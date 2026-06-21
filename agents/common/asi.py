"""Thin wrapper around the ASI:One LLM (OpenAI-compatible API).

ASI:One exposes an OpenAI-compatible endpoint at https://api.asi1.ai/v1, so we
reuse the `openai` client and just point it there. This keeps the orchestrator's
reasoning on Fetch.ai tech (counts toward the "Use of Fetch.ai technology" score).

If ASI1_API_KEY is unset we fall back to a deterministic keyword heuristic so the
whole pipeline still runs locally for testing without any keys.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

ASI1_BASE_URL = os.getenv("ASI1_BASE_URL", "https://api.asi1.ai/v1").strip()
ASI1_MODEL = os.getenv("ASI1_MODEL", "asi1-mini").strip()  # asi1-mini | asi1-fast | asi1-extended
_API_KEY = os.getenv("ASI1_API_KEY", "").strip()

_client = None
if _API_KEY:
    try:
        from openai import OpenAI

        _client = OpenAI(base_url=ASI1_BASE_URL, api_key=_API_KEY)
    except Exception:  # pragma: no cover - import/env issues shouldn't crash agents
        _client = None


def have_llm() -> bool:
    return _client is not None


def chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 800,
    model: Optional[str] = None,
) -> str:
    """Plain chat completion. Raises if no LLM is configured."""
    if not _client:
        raise RuntimeError("ASI1_API_KEY not set - cannot call ASI:One")
    resp = _client.chat.completions.create(
        model=model or ASI1_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_JSON_OBJ = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def _coerce_json(text: str) -> Optional[Any]:
    """Best-effort extraction of a JSON object from an LLM reply."""
    if not text:
        return None
    for pat in (_JSON_FENCE, _JSON_OBJ):
        m = pat.search(text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def chat_json(
    system: str,
    user: str,
    temperature: float = 0.1,
    max_tokens: int = 600,
) -> Optional[Dict[str, Any]]:
    """Ask the LLM for a JSON object and parse it. Returns None if unavailable."""
    if not _client:
        return None
    try:
        raw = chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception:
        return None
    return _coerce_json(raw)
