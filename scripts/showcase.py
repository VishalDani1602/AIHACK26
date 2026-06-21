"""CareLoop end-to-end showcase / smoke test.

Drives the LIVE agent mesh and prints everything in a demo-friendly way:
  health -> golden booking -> clinical evidence -> emergency -> new-chat reset
  -> Redis cache speedup -> live stats -> audit trail -> Agentverse profiles.

Prereqs: agents + voice running (./scripts/run_all.sh + uvicorn) and Redis up.
Run:  ./venv/bin/python -m scripts.showcase
"""
import sys
import time

import requests

from agents.common import config, store

ORCH = "http://127.0.0.1:8000/voice"
VOICE = "http://127.0.0.1:8080"

C = {"g": "\033[92m", "y": "\033[93m", "c": "\033[96m", "r": "\033[91m",
     "b": "\033[1m", "d": "\033[2m", "x": "\033[0m"}


def hdr(t):
    print(f"\n{C['b']}{C['c']}{'='*72}\n  {t}\n{'='*72}{C['x']}")


def ok(t):  print(f"  {C['g']}✓{C['x']} {t}")
def bad(t): print(f"  {C['r']}✗{C['x']} {t}")
def dim(t): print(f"  {C['d']}{t}{C['x']}")


def turn(session, text, pause=0.0):
    print(f"\n  {C['y']}🧑 \"{text}\"{C['x']}")
    try:
        r = requests.post(ORCH, json={"session_id": session, "text": text}, timeout=90)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        bad(f"request failed: {e}")
        return {}
    tag = {"emergency": C["r"], "done": C["g"], "awaiting_payment": C["y"]}.get(d.get("stage"), C["c"])
    print(f"  {tag}🤖 [{d.get('stage')}]{C['x']} {d.get('reply','').strip()}")
    if pause:
        time.sleep(pause)
    return d


def section_health():
    hdr("1 · SERVICE HEALTH")
    names = ["orchestrator", "triage", "provider", "cost", "scheduler", "payment", "evidence"]
    import socket
    for n in names:
        port = config.PORTS[n]
        s = socket.socket(); s.settimeout(1)
        up = s.connect_ex(("127.0.0.1", port)) == 0
        s.close()
        (ok if up else bad)(f"{n:13s} :{port}  {config.ADDRESSES.get(n,'')[:28]}…")
    try:
        h = requests.get(f"{VOICE}/api/health", timeout=5).json()
        ok(f"voice app :8080  deepgram={h.get('deepgram_key')}  redis={h.get('redis')}")
    except Exception:
        bad("voice app :8080 not reachable")
    (ok if store.enabled() else bad)(f"redis  {'connected' if store.enabled() else 'OFFLINE'}")


def section_golden():
    hdr("2 · GOLDEN PATH  (triage → provider → cost → Stripe deposit)")
    dim("A caregiver describes symptoms; agents coordinate to recommend + book.")
    turn("demo-golden", "my dad has had a bad cough and a low fever for five days, "
                         "he is on Medicare and we are in Berkeley")


def section_evidence():
    hdr("3 · CLINICAL EVIDENCE  (recruiting trials + drug safety)")
    dim("Serious/chronic condition → real ClinicalTrials.gov trials + openFDA drug notes.")
    turn("demo-evidence", "my mother was just diagnosed with early-stage breast cancer, "
                          "she is in San Francisco on Medicare and takes tamoxifen")


def section_emergency_and_reset():
    hdr("4 · EMERGENCY + NEW-CHAT RESET")
    dim("Red-flag symptoms → 911 (no booking). Then a NEW complaint in the same "
        "session starts fresh (no carry-over).")
    turn("demo-reset", "I'm having crushing chest pain and I can't breathe")
    turn("demo-reset", "ok, separately, I have an itchy rash on my arm, I'm in Berkeley on Medicare")


def section_redis():
    hdr("5 · REDIS  (cache speedup · live stats · audit trail)")
    if not store.enabled():
        bad("Redis not connected — skipping")
        return
    from agents.common import clinical, nppes
    t = time.time(); nppes.search_providers("Family Medicine", "Berkeley", "CA"); a = time.time() - t
    t = time.time(); nppes.search_providers("Family Medicine", "Berkeley", "CA"); b = time.time() - t
    ok(f"NPPES provider lookup: {a*1000:.0f}ms (API) → {b*1000:.0f}ms (cache)  "
       f"{C['g']}{a/max(b,1e-6):.0f}× faster{C['x']}")
    t = time.time(); clinical.search_trials("breast cancer", "California"); a = time.time() - t
    t = time.time(); clinical.search_trials("breast cancer", "California"); b = time.time() - t
    ok(f"ClinicalTrials lookup:  {a*1000:.0f}ms (API) → {b*1000:.0f}ms (cache)  "
       f"{C['g']}{a/max(b,1e-6):.0f}× faster{C['x']}")

    print(f"\n  {C['b']}Live stats (careloop:stats):{C['x']}")
    for k, v in sorted(store.get_stats().items()):
        print(f"    {k:22s} {v}")

    print(f"\n  {C['b']}Audit trail — recent events (careloop:audit Stream):{C['x']}")
    for e in store.recent_audit(8):
        extra = {k: v for k, v in e.items() if k not in ("id", "event")}
        dim(f"    {e.get('event','?'):20s} {extra}")


def section_links():
    hdr("6 · DELIVERABLES  (Agentverse agent profiles)")
    for n in ["orchestrator", "triage", "provider", "cost", "scheduler", "payment", "evidence"]:
        a = config.ADDRESSES.get(n, "")
        print(f"  {n:13s} https://agentverse.ai/agents/details/{a}/profile")
    print()
    dim("  Voice app:  http://127.0.0.1:8080")
    dim("  ASI:One:    chat with 'CareLoop' (orchestrator address above)")


def main():
    print(f"{C['b']}{C['g']}\n   ⊕ CareLoop — full showcase{C['x']}")
    dim("   voice-first, multi-agent healthcare concierge · Fetch.ai + Deepgram + Redis + Stripe")
    # quick reachability guard
    try:
        requests.get(f"{VOICE}/api/health", timeout=3)
    except Exception:
        bad("Services not reachable. Start them first:")
        dim("   ./scripts/run_all.sh  &&  ./venv/bin/python -m scripts.register_agents")
        dim("   ./venv/bin/uvicorn voice.backend:app --port 8080")
        sys.exit(1)
    section_health()
    section_golden()
    section_evidence()
    section_emergency_and_reset()
    section_redis()
    section_links()
    print(f"\n{C['b']}{C['g']}  ✓ Showcase complete.{C['x']}\n")


if __name__ == "__main__":
    main()
