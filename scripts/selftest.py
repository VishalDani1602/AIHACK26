"""End-to-end pipeline test with no agent transport (LocalSpecialists).

Runs two conversations:
  1. Golden path  -> triage -> real NPPES providers -> cost -> booking
  2. Red-flag path -> immediate 911 escalation

Works with or without ASI1_API_KEY (falls back to the naive extractor).
Run: ./venv/bin/python -m scripts.selftest
"""
import asyncio
import sys

from agents.common import asi
from agents.common.orchestration import LocalSpecialists, handle_turn, new_state


async def conversation(title, turns):
    print(f"\n{'='*70}\n{title}   (LLM={'ASI:One' if asi.have_llm() else 'fallback heuristic'})\n{'='*70}")
    state = new_state()
    state["session_id"] = "selftest"
    specialists = LocalSpecialists()
    for user in turns:
        print(f"\n🧑 USER: {user}")
        out = await handle_turn(state, user, specialists)
        print(f"🤖 CARELOOP [{out['stage']}]: {out['reply']}")
    return state


async def main():
    s1 = await conversation(
        "TEST 1 — Golden path (cough + fever, Medicare, Berkeley)",
        [
            "My dad has had a bad cough and a low fever for about five days. He's on Medicare.",
            "We're in Berkeley.",
            "Yes, please book it.",
        ],
    )
    assert s1["stage"] == "done", f"expected booking to complete, got {s1['stage']}"
    assert s1.get("last_booking_ics", "").startswith("BEGIN:VCALENDAR"), "missing .ics"
    print("\n✅ TEST 1 passed: reached a completed booking with calendar invite.")

    s2 = await conversation(
        "TEST 2 — Red-flag path (chest pain)",
        ["I'm having crushing chest pain and I can't breathe."],
    )
    assert s2["stage"] == "emergency", f"expected emergency, got {s2['stage']}"
    print("\n✅ TEST 2 passed: red-flag triggered 911 escalation, no booking.")

    print("\n🎉 All self-tests passed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as e:
        print(f"\n❌ SELF-TEST FAILED: {e}")
        sys.exit(1)
