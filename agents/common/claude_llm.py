"""Anthropic Claude client — used for clinical-reasoning quality in triage.

CareLoop's reasoning is split across two LLMs on purpose:
  - **ASI:One** drives the orchestrator (intent parsing, conversation, replies) —
    keeps the workflow on Fetch.ai tech.
  - **Claude** powers the **triage** clinical reasoning when ANTHROPIC_API_KEY is
    set, for higher-quality urgency/specialty judgments. Falls back to ASI:One,
    then to a keyword heuristic, so nothing breaks without a key.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from . import asi  # reuse the robust JSON extraction

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()

_client = None
if ANTHROPIC_API_KEY:
    try:
        from anthropic import Anthropic

        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception:
        _client = None


def have_claude() -> bool:
    return _client is not None


def chat(system: str, user: str, max_tokens: int = 700, temperature: float = 0.2,
         model: Optional[str] = None) -> str:
    if not _client:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    resp = _client.messages.create(
        model=model or ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def chat_json(system: str, user: str, temperature: float = 0.1,
              max_tokens: int = 700) -> Optional[Dict[str, Any]]:
    if not _client:
        return None
    try:
        raw = chat(system, user, max_tokens=max_tokens, temperature=temperature)
    except Exception:
        return None
    return asi._coerce_json(raw)
