"""Central config: per-agent seeds, ports, and derived addresses.

Seeds are fixed (overridable via env) so each agent keeps a stable Agentverse
address across restarts — which means the orchestrator can know the specialists'
addresses without any manual copy/paste.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

AGENTVERSE_API_KEY = os.getenv("AGENTVERSE_API_KEY", "").strip()

_README_DIR = Path(__file__).resolve().parents[1] / "readmes"


def readme(name: str) -> str | None:
    """Absolute path to an agent's profile README (published to Agentverse)."""
    p = _README_DIR / f"{name}.md"
    return str(p) if p.exists() else None

SEEDS = {
    "orchestrator": os.getenv("ORCHESTRATOR_SEED", "careloop-orchestrator-seed-2026"),
    "triage": os.getenv("TRIAGE_SEED", "careloop-triage-seed-2026"),
    "provider": os.getenv("PROVIDER_SEED", "careloop-provider-seed-2026"),
    "cost": os.getenv("COST_SEED", "careloop-cost-seed-2026"),
    "scheduler": os.getenv("SCHEDULER_SEED", "careloop-scheduler-seed-2026"),
}

PORTS = {
    "orchestrator": int(os.getenv("ORCHESTRATOR_PORT", "8000")),
    "triage": int(os.getenv("TRIAGE_PORT", "8001")),
    "provider": int(os.getenv("PROVIDER_PORT", "8002")),
    "cost": int(os.getenv("COST_PORT", "8003")),
    "scheduler": int(os.getenv("SCHEDULER_PORT", "8004")),
}


def _derive_addresses() -> dict:
    """Derive agent addresses from seeds (matches how uAgents derives them)."""
    try:
        from uagents.crypto import Identity

        return {name: Identity.from_seed(seed, 0).address for name, seed in SEEDS.items()}
    except Exception:
        return {}


ADDRESSES = _derive_addresses()

# Allow explicit env overrides (e.g. if running specialists elsewhere).
_ENV_ADDR = {
    "triage": "TRIAGE_AGENT_ADDRESS",
    "provider": "PROVIDER_AGENT_ADDRESS",
    "cost": "COST_AGENT_ADDRESS",
    "scheduler": "SCHEDULER_AGENT_ADDRESS",
    "orchestrator": "ORCHESTRATOR_AGENT_ADDRESS",
}
for _name, _var in _ENV_ADDR.items():
    _val = os.getenv(_var, "").strip()
    if _val:
        ADDRESSES[_name] = _val
