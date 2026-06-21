"""Auto-register every CareLoop agent's mailbox on Agentverse.

This replaces the manual "Connect -> Mailbox" click in the Agent Inspector.
Each running agent exposes a local POST /connect endpoint (the same one the
Inspector calls); we POST the Agentverse API token to it, and the agent registers
its mailbox + profile + README with Agentverse itself.

Prereqs:
  - AGENTVERSE_API_KEY set in .env
  - agents already running:  ./scripts/run_all.sh

Run:  ./venv/bin/python -m scripts.register_agents
"""
import sys
import time

import requests

from agents.common import config

TOKEN = config.AGENTVERSE_API_KEY
if not TOKEN:
    print("❌ AGENTVERSE_API_KEY is not set in .env"); sys.exit(1)

AGENTS = [
    ("orchestrator", config.PORTS["orchestrator"]),
    ("triage", config.PORTS["triage"]),
    ("provider", config.PORTS["provider"]),
    ("cost", config.PORTS["cost"]),
    ("scheduler", config.PORTS["scheduler"]),
]


def connect(name: str, port: int, attempts: int = 6) -> bool:
    url = f"http://127.0.0.1:{port}/connect"
    body = {"user_token": TOKEN, "agent_type": "mailbox"}
    for i in range(attempts):
        try:
            r = requests.post(url, json=body, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    return True
                print(f"   ↳ {name}: {data.get('detail')}")
                return False
            print(f"   ↳ {name}: HTTP {r.status_code} {r.text[:160]}")
        except requests.exceptions.ConnectionError:
            if i == 0:
                print(f"   ↳ {name}: agent not up yet on :{port}, waiting…")
            time.sleep(3)
            continue
        except Exception as exc:
            print(f"   ↳ {name}: {exc}")
            return False
    return False


def main():
    print(f"Registering {len(AGENTS)} CareLoop agents on Agentverse…\n")
    ok = 0
    for name, port in AGENTS:
        addr = config.ADDRESSES.get(name, "")
        success = connect(name, port)
        mark = "✅" if success else "❌"
        print(f"{mark} {name:13s} :{port}")
        if success:
            ok += 1
            print(f"     profile: https://agentverse.ai/agents/details/{addr}/profile")
    print(f"\n{ok}/{len(AGENTS)} registered.")
    if ok == len(AGENTS):
        print("\nNext: open https://asi1.ai , ensure 'Agents' is enabled, and chat with CareLoop.")
    else:
        print("\nSome failed — check the agents are running (./scripts/run_all.sh) and the token is valid.")
        sys.exit(1)


if __name__ == "__main__":
    main()
