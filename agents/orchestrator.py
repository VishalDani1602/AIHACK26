"""CareLoop Orchestrator Agent — the ASI:One-facing brain.

Two entry points, one brain:
  1. Agent Chat Protocol  -> discoverable & usable directly from ASI:One (no frontend).
  2. REST POST /voice      -> used by the Deepgram voice web app.

Both funnel into orchestration.handle_turn, which coordinates the specialist agents
(triage -> provider-finder -> cost -> scheduler) via ctx.send_and_receive. Each
remote call falls back to in-process logic if a specialist is unreachable, so the
orchestrator always answers.
"""
from datetime import datetime, timezone
from uuid import uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agents.common import config
from agents.common.models import (
    BookingResult,
    CostResult,
    EvidenceResult,
    PaymentLinkResult,
    PaymentVerifyResult,
    ProviderResult,
    TriageResult,
    VoiceRequest,
    VoiceResponse,
)
from agents.common.orchestration import LocalSpecialists, handle_turn, new_state
from agents.common.prompts import DISCLAIMER

agent = Agent(
    name="careloop-orchestrator",
    seed=config.SEEDS["orchestrator"],
    port=config.PORTS["orchestrator"],
    mailbox=True,
    publish_agent_details=True,
    readme_path=config.readme("orchestrator"),
    description=(
        "CareLoop — a voice-first healthcare-access concierge. Describe a health "
        "concern and CareLoop triages urgency, finds real in-network providers "
        "(CMS NPPES), estimates your out-of-pocket cost, and books an appointment. "
        "Navigation only, not medical advice; emergencies are routed to 911."
    ),
)

GREETING = (
    "Hi, I'm CareLoop. " + DISCLAIMER + "\n\n"
    "Tell me what's going on — for example, \"my dad has had a bad cough and fever "
    "for five days, he's on Medicare in Berkeley\" — and I'll find and book care."
)


# --------------------------------------------------------------------------- #
# Specialist client backed by real agent-to-agent messaging (+ local fallback)
# --------------------------------------------------------------------------- #
class AgentSpecialists:
    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.local = LocalSpecialists()

    async def _call(self, name, req, rtype, local_fn):
        addr = config.ADDRESSES.get(name)
        if addr and addr != agent.address:
            try:
                reply, status = await self.ctx.send_and_receive(
                    addr, req, response_type=rtype, timeout=25
                )
                if isinstance(reply, rtype):
                    return reply
                self.ctx.logger.warning(f"{name}: unexpected reply ({status}); local fallback")
            except Exception as exc:
                self.ctx.logger.warning(f"{name}: messaging failed ({exc}); local fallback")
        return await local_fn(req)

    async def triage(self, req):
        return await self._call("triage", req, TriageResult, self.local.triage)

    async def find_providers(self, req):
        return await self._call("provider", req, ProviderResult, self.local.find_providers)

    async def estimate_cost(self, req):
        return await self._call("cost", req, CostResult, self.local.estimate_cost)

    async def book(self, req):
        return await self._call("scheduler", req, BookingResult, self.local.book)

    async def create_payment(self, req):
        return await self._call("payment", req, PaymentLinkResult, self.local.create_payment)

    async def verify_payment(self, req):
        return await self._call("payment", req, PaymentVerifyResult, self.local.verify_payment)

    async def get_evidence(self, req):
        return await self._call("evidence", req, EvidenceResult, self.local.get_evidence)


# --------------------------------------------------------------------------- #
# Session state helpers (persisted in agent storage)
# --------------------------------------------------------------------------- #
def load_state(ctx: Context, key: str) -> dict:
    raw = ctx.storage.get(key)
    state = raw if isinstance(raw, dict) and raw.get("stage") else new_state()
    state["session_id"] = key
    return state


def save_state(ctx: Context, key: str, state: dict):
    ctx.storage.set(key, state)


# --------------------------------------------------------------------------- #
# Entry point 1: Agent Chat Protocol (ASI:One)
# --------------------------------------------------------------------------- #
chat_proto = Protocol(spec=chat_protocol_spec)


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc), acknowledged_msg_id=msg.msg_id))

    text_parts, is_start = [], False
    for item in msg.content:
        if isinstance(item, TextContent):
            text_parts.append(item.text)
        elif isinstance(item, StartSessionContent):
            is_start = True
    text = " ".join(text_parts).strip()

    state = load_state(ctx, sender)

    # New ASI:One chat (start-session marker) -> wipe any prior state for this sender,
    # so closing a chat and opening a new one always starts clean.
    if is_start:
        state = new_state()
        state["session_id"] = sender
        save_state(ctx, sender, state)
        if not text:
            await _send_chat(ctx, sender, GREETING)
            return

    if not text:
        return

    out = await handle_turn(state, text, AgentSpecialists(ctx))
    save_state(ctx, sender, state)
    await _send_chat(ctx, sender, out["reply"], end=out["stage"] in ("done", "emergency"))


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


async def _send_chat(ctx: Context, dest: str, text: str, end: bool = False):
    content = [TextContent(type="text", text=text)]
    if end:
        content.append(EndSessionContent(type="end-session"))
    await ctx.send(dest, ChatMessage(
        timestamp=datetime.now(timezone.utc), msg_id=uuid4(), content=content))


# --------------------------------------------------------------------------- #
# Entry point 2: REST POST /voice (Deepgram voice web app)
# --------------------------------------------------------------------------- #
@agent.on_rest_post("/voice", VoiceRequest, VoiceResponse)
async def voice_endpoint(ctx: Context, req: VoiceRequest) -> VoiceResponse:
    key = f"voice:{req.session_id}"
    text = req.text.strip()
    state = load_state(ctx, key)
    # Explicit plan from a UI selector wins; if it changes with no text, re-evaluate.
    if req.insurance.strip():
        plan = req.insurance.strip().lower()
        if not text and state.get("insurance") != plan:
            text = f"my insurance is {plan}"
        state["insurance"] = plan
    if not text:
        save_state(ctx, key, state)
        return VoiceResponse(session_id=req.session_id, reply=GREETING, stage="collecting")
    out = await handle_turn(state, text, AgentSpecialists(ctx))
    save_state(ctx, key, state)
    return VoiceResponse(
        session_id=req.session_id, reply=out["reply"],
        stage=out["stage"], emergency=out["emergency"],
        card=out.get("card"), actions=out.get("actions"))


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Orchestrator address: {agent.address}")
    ctx.logger.info(f"Routing to specialists: {config.ADDRESSES}")
    ctx.logger.info(f"Voice REST endpoint: POST http://127.0.0.1:{config.PORTS['orchestrator']}/voice")


agent.include(chat_proto, publish_manifest=True)


if __name__ == "__main__":
    agent.run()
