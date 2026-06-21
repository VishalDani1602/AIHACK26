"""Pure business logic for CareLoop specialists.

Everything here is plain, testable functions with no agent/transport dependency.
The specialist agents are thin wrappers that call these; this also lets us run the
whole pipeline end-to-end locally (scripts/selftest.py) without Agentverse.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from . import asi, claude_llm, store
from .models import Provider, TriageResult
from .prompts import ALLOWED_SPECIALTIES, TRIAGE_SYSTEM

_DATA = Path(__file__).resolve().parents[2] / "data"
TAXONOMY_MAP: Dict[str, dict] = json.loads((_DATA / "taxonomy_map.json").read_text())
COST_TABLE: Dict = json.loads((_DATA / "cost_table.json").read_text())


# --------------------------------------------------------------------------- #
# Triage
# --------------------------------------------------------------------------- #

# Hard red-flag rules run BEFORE the LLM. These always force an emergency result.
RED_FLAG_PATTERNS: List[Tuple[str, str]] = [
    (r"chest (pain|pressure|tightness)|crushing chest", "chest pain / pressure"),
    (r"can'?t breathe|cannot breathe|difficulty breathing|struggling to breathe|gasping", "difficulty breathing"),
    (r"face (droop|drooping)|slurred speech|one side.*(numb|weak)|sudden weakness|stroke", "possible stroke signs"),
    (r"unconscious|unresponsive|passed out|fainted and", "loss of consciousness"),
    (r"severe bleeding|bleeding (a lot|heavily)|won'?t stop bleeding", "severe bleeding"),
    (r"suicidal|kill myself|end my life|want to die", "suicidal ideation"),
    (r"overdose|took too many pills", "possible overdose"),
    (r"anaphylaxis|throat (closing|swelling)|can'?t swallow and", "possible anaphylaxis"),
    (r"seizure|convulsing", "seizure"),
    (r"blue lips|turning blue", "cyanosis"),
]


def check_red_flags(symptoms: str) -> List[str]:
    s = symptoms.lower()
    return [label for pat, label in RED_FLAG_PATTERNS if re.search(pat, s)]


def _specialty_to_taxonomy(specialty: str) -> Tuple[str, str]:
    entry = TAXONOMY_MAP.get(specialty)
    if not entry:
        entry = TAXONOMY_MAP["Primary Care"]
        specialty = "Primary Care"
    return specialty, entry["taxonomy"]


def _heuristic_specialty(symptoms: str) -> str:
    s = symptoms.lower()
    table = [
        ("Cardiology", ["heart", "palpitation", "blood pressure"]),
        ("Dermatology", ["rash", "skin", "mole", "acne", "itch"]),
        ("Orthopedics", ["knee", "shoulder", "fracture", "sprain", "back pain", "joint"]),
        ("Psychiatry", ["anxiety", "depress", "panic", "mental", "stress"]),
        ("Pulmonology", ["cough", "asthma", "wheez", "lung"]),
        ("Gastroenterology", ["stomach", "nausea", "diarrhea", "abdominal", "vomit"]),
        ("ENT", ["ear", "throat", "sinus", "nose"]),
        ("Pediatrics", ["my child", "my son", "my daughter", "baby", "toddler"]),
        ("Ophthalmology", ["eye", "vision", "blurry"]),
        ("Dentistry", ["tooth", "teeth", "gum", "dental"]),
        ("OB-GYN", ["pregnan", "period", "menstr"]),
    ]
    for specialty, kws in table:
        if any(k in s for k in kws):
            return specialty
    return "Primary Care"


def triage(session_id: str, symptoms: str, patient_age=None) -> TriageResult:
    red_flags = check_red_flags(symptoms)
    if red_flags:
        specialty, taxonomy = "Urgent Care", TAXONOMY_MAP["Urgent Care"]["taxonomy"]
        return TriageResult(
            session_id=session_id,
            urgency="emergency",
            recommended_specialty=specialty,
            taxonomy=taxonomy,
            red_flags=red_flags,
            advice="These symptoms can be life-threatening. Call 911 or go to the nearest ER now.",
            emergency=True,
        )

    # Shared Redis cache: identical symptoms skip the ASI:One call (saves latency + tokens).
    cache_key = "triage:" + store.hash_key(symptoms.lower().strip(), patient_age or "")
    cached = store.cache_get_json(cache_key)
    if cached:
        store.incr_stat("triage_cache_hit")
        specialty = cached["specialty"]
        urgency = cached["urgency"]
        advice = cached["advice"]
        llm_flags = cached.get("red_flags", [])
        condition = cached.get("condition", "")
        chronic = cached.get("chronic", False)
    else:
        user_msg = f"Patient age: {patient_age or 'unknown'}\nConcern: {symptoms}"
        # Prefer Claude for clinical-reasoning quality; fall back to ASI:One, then heuristic.
        data = claude_llm.chat_json(TRIAGE_SYSTEM, user_msg) if claude_llm.have_claude() else None
        engine = "claude" if data else ""
        if data is None:
            data = asi.chat_json(TRIAGE_SYSTEM, user_msg)
            engine = "asi1" if data else "heuristic"
        if engine:
            store.incr_stat(f"triage_engine_{engine}")
        if data and data.get("recommended_specialty"):
            specialty = data.get("recommended_specialty", "Primary Care")
            if specialty not in ALLOWED_SPECIALTIES:
                specialty = "Primary Care"
            urgency = data.get("urgency", "routine")
            advice = data.get("advice", "")
            llm_flags = data.get("red_flags", []) or []
            condition = (data.get("condition") or "").strip()
            chronic = bool(data.get("chronic", False))
        else:
            specialty = _heuristic_specialty(symptoms)
            urgency = "routine"
            advice = "Based on what you've shared, a visit with the right clinician is a good next step."
            llm_flags = []
            condition = ""
            chronic = False
        store.incr_stat("triage_llm_call")
        store.cache_set_json(cache_key, {
            "specialty": specialty, "urgency": urgency, "advice": advice,
            "red_flags": llm_flags, "condition": condition, "chronic": chronic}, ttl=3600)

    specialty, taxonomy = _specialty_to_taxonomy(specialty)
    emergency = urgency == "emergency"
    return TriageResult(
        session_id=session_id,
        urgency=urgency,
        recommended_specialty=specialty,
        taxonomy=taxonomy,
        red_flags=llm_flags,
        advice=advice,
        emergency=emergency,
        condition=condition,
        chronic=chronic,
    )


def visit_type_for_specialty(specialty: str) -> str:
    entry = TAXONOMY_MAP.get(specialty, TAXONOMY_MAP["Primary Care"])
    return entry["visit_type"]


# --------------------------------------------------------------------------- #
# Cost estimate
# --------------------------------------------------------------------------- #

# Rough regional cost-of-care multipliers (illustrative, by US state).
_REGION_COST = {
    "CA": 1.25, "NY": 1.30, "MA": 1.22, "NJ": 1.18, "CT": 1.18, "WA": 1.15,
    "DC": 1.25, "HI": 1.20, "CO": 1.08, "IL": 1.05, "PA": 1.02, "AZ": 1.00,
    "FL": 1.00, "GA": 0.97, "NC": 0.96, "TX": 0.96, "MI": 0.93, "OH": 0.92,
}


def _region_multiplier(region: str) -> float:
    return _REGION_COST.get((region or "").strip().upper(), 1.0)


def _provider_multiplier(seed: str) -> float:
    """Deterministic per-provider price variance (~0.85x–1.25x of the area baseline)."""
    if not seed:
        return 1.0
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 1000
    return 0.85 + (h / 1000.0) * 0.40


def _round5(x: float) -> int:
    return int(round(x / 5.0) * 5)


def estimate_cost(visit_type: str, insurance: str = "",
                  provider_seed: str = "", region: str = "") -> Tuple[float, float, str]:
    base0 = COST_TABLE["visit_base_cost"].get(visit_type, COST_TABLE["visit_base_cost"]["primary_care"])
    # Billed amount varies by region (cost of care) and by the specific provider.
    base = base0 * _region_multiplier(region) * _provider_multiplier(provider_seed)
    visit = visit_type.replace("_", " ")
    plan_key = (insurance or "").lower().strip()
    plan = COST_TABLE["plans"].get(plan_key)

    if not plan:
        # Unknown/no plan: self-pay billed range for THIS provider/area.
        low, high = _round5(base * 0.7), _round5(base * 1.15)
        return float(low), float(high), (
            f"Estimated self-pay cost for a {visit} visit at this provider is about "
            f"${low}–${high}. Share your insurance for a tighter, plan-based estimate."
        )

    copay = plan["copay"]
    coins = plan["coinsurance"]
    ded = plan["deductible_remaining"]

    if copay and ded <= 0:
        low = high = float(copay)
        why = f"With {plan['label']}, you'd typically owe your ${copay} copay."
    else:
        # If deductible not met, you pay billed up to the deductible, then coinsurance.
        toward_ded = min(base, ded)
        after_ded = max(base - ded, 0)
        oop = toward_ded + after_ded * coins + (copay if ded <= 0 else 0)
        low = _round5(max(oop * 0.85, copay))
        high = _round5(oop * 1.15)
        why = (
            f"With {plan['label']} (≈${ded:.0f} deductible left, {coins*100:.0f}% coinsurance), "
            f"this {visit} visit (≈${_round5(base)} billed) would land around ${low}–${high}."
        )
    return float(low), float(high), why


# --------------------------------------------------------------------------- #
# Booking
# --------------------------------------------------------------------------- #

def _conf_code() -> str:
    return "CL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _parse_slot_to_dt(slot: str) -> datetime:
    """Best-effort: turn a synthesized slot phrase into a concrete datetime."""
    now = datetime.now(timezone.utc)
    day_offset = 1
    m = re.search(r"in (\d+) days", slot)
    if m:
        day_offset = int(m.group(1))
    elif "tomorrow" in slot:
        day_offset = 1
    hour, minute = 10, 0
    tm = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", slot, re.I)
    if tm:
        hour, minute = int(tm.group(1)), int(tm.group(2))
        if tm.group(3).upper() == "PM" and hour != 12:
            hour += 12
        if tm.group(3).upper() == "AM" and hour == 12:
            hour = 0
    return (now + timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def _make_ics(provider_name: str, address: str, start: datetime, reason: str, code: str) -> str:
    end = start + timedelta(minutes=30)
    fmt = "%Y%m%dT%H%M%SZ"
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//CareLoop//EN",
            "BEGIN:VEVENT",
            f"UID:{code}@careloop",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime(fmt)}",
            f"DTSTART:{start.strftime(fmt)}",
            f"DTEND:{end.strftime(fmt)}",
            f"SUMMARY:Appointment with {provider_name}",
            f"LOCATION:{address}",
            f"DESCRIPTION:CareLoop booking {code}. Reason: {reason or 'consultation'}",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
    )


def book(session_id: str, provider_name: str, provider_address: str = "", slot: str = "",
         patient_name: str = "the patient", reason: str = "") -> Tuple[str, str, str]:
    """Returns (confirmation_code, summary, ics_text)."""
    code = _conf_code()
    start = _parse_slot_to_dt(slot or "tomorrow at 10:00 AM")
    when = start.strftime("%A, %B %-d at %-I:%M %p")
    summary = (
        f"Booked: {provider_name}"
        + (f" — {provider_address}" if provider_address else "")
        + f". {when}. Confirmation {code}."
    )
    ics = _make_ics(provider_name, provider_address, start, reason, code)
    return code, summary, ics
