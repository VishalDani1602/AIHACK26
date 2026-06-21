"""CareLoop orchestration core — the conversation brain.

`handle_turn` is transport-agnostic: it talks to specialists through a small
`Specialists` interface. In production the orchestrator agent injects an
implementation backed by `ctx.send_and_receive` (real agent-to-agent messaging);
tests/fallback inject one backed by direct logic calls.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Protocol

from . import asi, logic, store, stripe_pay
from .models import (
    BookingRequest,
    BookingResult,
    CostRequest,
    CostResult,
    PaymentLinkRequest,
    PaymentLinkResult,
    PaymentVerifyRequest,
    PaymentVerifyResult,
    Provider,
    ProviderRequest,
    ProviderResult,
    TriageRequest,
    TriageResult,
)
from .prompts import DISCLAIMER, EMERGENCY_BANNER, ORCHESTRATOR_SYSTEM


class Specialists(Protocol):
    async def triage(self, req: TriageRequest) -> Optional[TriageResult]: ...
    async def find_providers(self, req: ProviderRequest) -> Optional[ProviderResult]: ...
    async def estimate_cost(self, req: CostRequest) -> Optional[CostResult]: ...
    async def book(self, req: BookingRequest) -> Optional[BookingResult]: ...
    async def create_payment(self, req: PaymentLinkRequest) -> Optional[PaymentLinkResult]: ...
    async def verify_payment(self, req: PaymentVerifyRequest) -> Optional[PaymentVerifyResult]: ...


def new_state() -> Dict:
    return {
        "stage": "collecting",
        "symptoms": "",
        "patient_age": None,
        "patient_name": "",
        "city": "",
        "state": "",
        "postal_code": "",
        "insurance": "",
        "specialty": "",
        "taxonomy": "",
        "pending": None,   # {"provider": Provider.dict(), "cost_low":, "cost_high":, "cost_why":}
        "payment": None,   # {"stripe_session_id", "checkout_url", "amount"}
        "skip_payment": False,
        "deposit_paid": 0.0,
    }


# --------------------------------------------------------------------------- #
# Slot extraction (LLM preferred, naive regex fallback)
# --------------------------------------------------------------------------- #
_INS_KEYWORDS = [
    ("medicare", ["medicare"]),
    ("medicaid", ["medicaid", "medi-cal", "medical card"]),
    ("high_deductible", ["high deductible", "hdhp", "high-deductible"]),
    ("ppo", ["ppo"]),
    ("hmo", ["hmo", "kaiser"]),
    ("uninsured", ["uninsured", "no insurance", "self pay", "self-pay"]),
]
_KNOWN_CITIES = {
    "berkeley": "CA", "oakland": "CA", "san francisco": "CA", "sf": "CA",
    "emeryville": "CA", "alameda": "CA", "richmond": "CA", "san jose": "CA",
}
_YES = re.compile(r"\b(yes|yeah|yep|sure|book it|sounds good|ok|okay|please do|do it|go ahead|confirm|done|paid|finished|complete[d]?)\b", re.I)
_NO = re.compile(r"\b(no|nope|nah|different|someone else|another|other doctor|not that|skip)\b", re.I)


def _naive_extract(state: Dict, text: str) -> str:
    t = text.lower()
    intent = "provide_info"
    if state.get("stage") in ("confirming", "awaiting_payment"):
        if _YES.search(t):
            intent = "confirm"
        elif _NO.search(t):
            intent = "decline"
    if re.search(r"\b(start over|restart|new problem|different problem)\b", t):
        intent = "restart"

    # insurance
    if not state.get("insurance"):
        for key, kws in _INS_KEYWORDS:
            if any(k in t for k in kws):
                state["insurance"] = key
                break
    # zip
    if not state.get("postal_code"):
        m = re.search(r"\b(\d{5})\b", t)
        if m:
            state["postal_code"] = m.group(1)
    # city/state
    if not state.get("city"):
        for city, st in _KNOWN_CITIES.items():
            if city in t:
                state["city"] = "San Francisco" if city == "sf" else city.title()
                state["state"] = st
                break
    # age
    if state.get("patient_age") is None:
        m = re.search(r"\b(\d{1,3})\s*(?:years?\s*old|yo|y/o)\b", t)
        if m:
            state["patient_age"] = int(m.group(1))
    # symptoms: accumulate when giving info (not a pure yes/no)
    if intent == "provide_info" and not (_YES.search(t) or _NO.search(t)) and len(text.strip()) > 2:
        existing = state.get("symptoms", "")
        state["symptoms"] = (existing + " " + text).strip() if existing else text.strip()
    return intent


def _llm_extract(state: Dict, text: str) -> str:
    known = {k: state.get(k) for k in
             ["symptoms", "patient_age", "patient_name", "city", "state", "postal_code", "insurance"]}
    data = asi.chat_json(
        ORCHESTRATOR_SYSTEM,
        f"Info so far (JSON): {known}\nUser's latest message: {text}",
    )
    if not data:
        return _naive_extract(state, text)
    for key in ["symptoms", "patient_name", "city", "state", "postal_code", "insurance"]:
        val = (data.get(key) or "").strip() if isinstance(data.get(key), str) else data.get(key)
        if val:
            state[key] = val
    if isinstance(data.get("patient_age"), int):
        state["patient_age"] = data["patient_age"]
    intent = data.get("intent", "provide_info")
    if intent not in ("provide_info", "confirm", "decline", "restart", "smalltalk"):
        intent = "provide_info"
    return intent


# --------------------------------------------------------------------------- #
# Main turn handler
# --------------------------------------------------------------------------- #
async def handle_turn(state: Dict, user_text: str, specialists: Specialists) -> Dict:
    session_id = state.get("session_id", "session")
    intent = _llm_extract(state, user_text) if asi.have_llm() else _naive_extract(state, user_text)

    # Robust override: in a yes/no stage, an explicit affirmation/decline wins over the LLM's guess.
    if state.get("stage") in ("confirming", "awaiting_payment"):
        if _YES.search(user_text):
            intent = "confirm"
        elif _NO.search(user_text):
            intent = "decline"

    if intent == "restart":
        sid = session_id
        state.clear()
        state.update(new_state())
        state["session_id"] = sid
        return _out(state, "No problem — let's start fresh. What's going on, and who is it for?", "collecting")

    # ---- Awaiting Stripe deposit payment ----
    if state.get("stage") == "awaiting_payment" and state.get("payment"):
        if intent == "confirm":
            return await _verify_and_book(state, specialists)
        if intent == "decline":
            state["skip_payment"] = True
            return _out(state, "No problem — I won't charge a deposit. Say \"yes\" and I'll book it now.", "confirming")
        url = state["payment"]["checkout_url"]
        return _out(state, f"I don't see the payment yet. You can pay the deposit here:\n\n{url}\n\nThen just say \"done\".", "awaiting_payment")

    # ---- Confirming an appointment ----
    if state.get("stage") == "confirming" and state.get("pending"):
        if intent == "confirm":
            return await _proceed_after_confirm(state, specialists)
        if intent == "decline":
            return _out(state,
                        "Okay. I can look for a different provider or another time — which would you prefer?",
                        "confirming")
        # otherwise fall through and treat new info below

    # ---- Collecting required info ----
    if not state.get("symptoms"):
        return _out(state, f"{DISCLAIMER}\n\nTell me what's going on and I'll help you find care. "
                           "What symptoms are you (or your loved one) having?", "collecting")

    # Run triage as soon as we have symptoms (it may flag an emergency immediately).
    tri = await specialists.triage(
        TriageRequest(session_id=session_id, symptoms=state["symptoms"], patient_age=state.get("patient_age"))
    )
    if tri is None:
        return _out(state, "Sorry, I had trouble assessing that. Could you describe the symptoms again?", "collecting")

    if tri.emergency:
        state["stage"] = "emergency"
        store.audit("emergency", {"session": session_id, "red_flags": tri.red_flags})
        store.incr_stat("emergencies")
        flags = f" ({', '.join(tri.red_flags)})" if tri.red_flags else ""
        return _out(state, f"{EMERGENCY_BANNER}{flags}\n\n{tri.advice}", "emergency", emergency=True)

    store.audit("triage", {"session": session_id, "urgency": tri.urgency,
                           "specialty": tri.recommended_specialty})
    state["specialty"] = tri.recommended_specialty
    state["taxonomy"] = tri.taxonomy

    # Need a location to search for providers.
    if not (state.get("city") or state.get("postal_code")):
        return _out(state,
                    f"{tri.advice} I'd start with **{tri.recommended_specialty}**. "
                    "What city or ZIP code should I search near?",
                    "collecting")

    # Find providers.
    pr = await specialists.find_providers(ProviderRequest(
        session_id=session_id, taxonomy=tri.taxonomy, city=state.get("city", ""),
        state=state.get("state", ""), postal_code=state.get("postal_code", ""),
        insurance=state.get("insurance", ""), limit=3,
    ))
    providers = pr.providers if pr else []
    if not providers:
        return _out(state,
                    f"I couldn't find a {tri.recommended_specialty} provider near "
                    f"{state.get('city') or state.get('postal_code')}. Want me to try a nearby area?",
                    "collecting")

    top = providers[0]
    visit_type = logic.visit_type_for_specialty(tri.recommended_specialty)
    cr = await specialists.estimate_cost(CostRequest(
        session_id=session_id, visit_type=visit_type, insurance=state.get("insurance", "")))
    cost_low = cr.estimate_low if cr else 0.0
    cost_high = cr.estimate_high if cr else 0.0
    cost_why = cr.explanation if cr else ""

    state["pending"] = {
        "provider": top.dict(),
        "cost_low": cost_low, "cost_high": cost_high, "cost_why": cost_why,
        "visit_type": visit_type,
    }
    state["stage"] = "confirming"

    ins_note = ""
    if state.get("insurance"):
        ins_note = " that accepts your plan" if top.accepts_insurance else " (please confirm they take your plan)"
    reply = (
        f"{tri.advice} I'd start with **{tri.recommended_specialty}** — and good news, this isn't an emergency.\n\n"
        f"The best match near {state.get('city') or state.get('postal_code')}{ins_note} is "
        f"**{top.name}** ({top.specialty}) at {top.address}, "
        f"with an opening **{top.next_slot}**.\n\n"
        f"Estimated cost: **${cost_low:.0f}–${cost_high:.0f}**. {cost_why}\n\n"
        f"Want me to book {top.next_slot} for you?"
    )
    return _out(state, reply, "confirming")


async def _proceed_after_confirm(state: Dict, specialists: Specialists) -> Dict:
    """After the user confirms, take a refundable deposit via Stripe (if enabled), then book."""
    deposit = stripe_pay.DEPOSIT_USD
    if state.get("skip_payment") or deposit <= 0:
        return await _do_booking(state, specialists)

    prov = state["pending"]["provider"]
    plr = await specialists.create_payment(PaymentLinkRequest(
        session_id=state.get("session_id", "session"),
        amount_usd=deposit,
        description=f"CareLoop booking deposit — {prov['name']}",
    ))
    if not plr or not plr.enabled or not plr.checkout_url:
        # Stripe not configured / failed -> just book.
        return await _do_booking(state, specialists)

    state["payment"] = {
        "stripe_session_id": plr.stripe_session_id,
        "checkout_url": plr.checkout_url,
        "amount": plr.amount_usd,
    }
    store.audit("payment_requested", {"session": state.get("session_id", ""),
                                      "amount": str(plr.amount_usd),
                                      "stripe_session": plr.stripe_session_id})
    store.incr_stat("payments_requested")
    reply = (
        f"Almost done. To hold your appointment, please pay a **refundable ${plr.amount_usd:.0f} deposit** "
        f"(applied to your visit) on this secure Stripe page:\n\n{plr.checkout_url}\n\n"
        f"You can use the test card 4242 4242 4242 4242, any future date and CVC. "
        f"Once it's paid, say \"done\" and I'll confirm the booking."
    )
    return _out(state, reply, "awaiting_payment")


async def _verify_and_book(state: Dict, specialists: Specialists) -> Dict:
    pay = state["payment"]
    vr = await specialists.verify_payment(PaymentVerifyRequest(
        session_id=state.get("session_id", "session"),
        stripe_session_id=pay["stripe_session_id"],
    ))
    if vr and vr.paid:
        state["deposit_paid"] = pay.get("amount", 0.0)
        store.audit("payment_paid", {"session": state.get("session_id", ""),
                                     "amount": str(pay.get("amount", 0.0))})
        store.incr_stat("payments_paid")
        return await _do_booking(state, specialists)
    status = vr.status if vr else "unknown"
    return _out(state,
                f"I don't see the deposit completed yet (status: {status}). "
                f"Once the payment goes through, say \"done\". Link: {pay['checkout_url']}",
                "awaiting_payment")


async def _do_booking(state: Dict, specialists: Specialists) -> Dict:
    pending = state["pending"]
    prov = pending["provider"]
    br = await specialists.book(BookingRequest(
        session_id=state.get("session_id", "session"),
        provider_name=prov["name"], provider_address=prov.get("address", ""),
        slot=prov.get("next_slot", ""), patient_name=state.get("patient_name", "the patient"),
        reason=state.get("symptoms", ""),
    ))
    if br is None:
        return _out(state, "I hit a snag booking that. Want me to try again?", "confirming")
    state["stage"] = "done"
    state["last_booking_ics"] = br.ics
    store.audit("booking_confirmed", {"session": state.get("session_id", ""),
                                      "provider": prov["name"],
                                      "confirmation": br.confirmation_code})
    store.incr_stat("bookings")
    deposit_note = ""
    if state.get("deposit_paid"):
        deposit_note = f" Your ${state['deposit_paid']:.0f} refundable deposit was received (applied to your visit)."
    reply = (
        f"✅ {br.summary}{deposit_note}\n\n"
        f"I've prepared a calendar invite and a summary you can share. "
        f"Reminder: {DISCLAIMER} Is there anything else I can help with?"
    )
    return _out(state, reply, "done")


def _out(state: Dict, reply: str, stage: str, emergency: bool = False) -> Dict:
    state["stage"] = stage
    return {"reply": reply, "stage": stage, "emergency": emergency}


# --------------------------------------------------------------------------- #
# Local (in-process) specialist implementation — used by selftest & as fallback
# --------------------------------------------------------------------------- #
class LocalSpecialists:
    """Calls the pure logic directly. No agent transport."""

    async def triage(self, req: TriageRequest):
        return logic.triage(req.session_id, req.symptoms, req.patient_age)

    async def find_providers(self, req: ProviderRequest):
        from . import nppes
        try:
            providers = nppes.search_providers(
                req.taxonomy, req.city, req.state, req.postal_code, req.insurance, req.limit)
            note = "Live provider data from the CMS NPPES registry."
            if not providers:
                providers = nppes.fallback_providers(req.taxonomy, req.city, req.limit)
                note = "Showing sample providers (no NPPES match)."
        except Exception:
            providers = nppes.fallback_providers(req.taxonomy, req.city, req.limit)
            note = "Showing sample providers (NPPES unavailable)."
        return ProviderResult(session_id=req.session_id, providers=providers, note=note)

    async def estimate_cost(self, req: CostRequest):
        low, high, why = logic.estimate_cost(req.visit_type, req.insurance)
        return CostResult(session_id=req.session_id, estimate_low=low, estimate_high=high, explanation=why)

    async def book(self, req: BookingRequest):
        code, summary, ics = logic.book(
            req.session_id, req.provider_name, req.provider_address, req.slot,
            req.patient_name, req.reason)
        return BookingResult(session_id=req.session_id, confirmation_code=code, summary=summary, ics=ics)

    async def create_payment(self, req: PaymentLinkRequest):
        if not stripe_pay.enabled():
            return PaymentLinkResult(session_id=req.session_id, enabled=False)
        try:
            sid, url = stripe_pay.create_checkout(req.amount_usd, req.description)
            return PaymentLinkResult(session_id=req.session_id, enabled=True,
                                     checkout_url=url, stripe_session_id=sid, amount_usd=req.amount_usd)
        except Exception:
            return PaymentLinkResult(session_id=req.session_id, enabled=False)

    async def verify_payment(self, req: PaymentVerifyRequest):
        paid, status = stripe_pay.verify(req.stripe_session_id)
        return PaymentVerifyResult(session_id=req.session_id, paid=paid, status=status)
