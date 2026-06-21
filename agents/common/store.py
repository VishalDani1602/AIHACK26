"""Redis layer for CareLoop — shared cache, session store, audit trail, and stats.

Redis is used here *beyond plain caching*:
  - **Cache** (with TTL): NPPES provider lookups + triage results, shared across
    every agent process (the provider agent's cache benefits the orchestrator's
    local fallback, the voice path, etc.).
  - **Session store** (Hash + TTL): conversation state that survives restarts and
    is shared between the voice backend and the agent mesh.
  - **Audit trail** (Streams): an append-only, timestamped log of every clinical
    decision / payment / booking — a real healthcare audit log.
  - **Live stats** (Hash counters): bookings, emergencies, cache hits, etc.

Everything degrades gracefully: if Redis is unreachable, caches simply miss,
sessions fall back to in-memory, and audit/stat calls are no-ops.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
PREFIX = "careloop"
AUDIT_STREAM = f"{PREFIX}:audit"
STATS_KEY = f"{PREFIX}:stats"

_client = None
if REDIS_URL:
    try:
        import redis

        _c = redis.Redis.from_url(
            REDIS_URL, decode_responses=True,
            socket_connect_timeout=1, socket_timeout=1,
        )
        _c.ping()
        _client = _c
    except Exception:
        _client = None


def enabled() -> bool:
    return _client is not None


def _safe(fn: Callable, default=None):
    try:
        return fn()
    except Exception:
        return default


def hash_key(*parts: Any) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Cache (with TTL)
# --------------------------------------------------------------------------- #
def cache_get_json(key: str) -> Optional[Any]:
    if not _client:
        return None
    raw = _safe(lambda: _client.get(f"{PREFIX}:cache:{key}"))
    return json.loads(raw) if raw else None


def cache_set_json(key: str, value: Any, ttl: int = 3600) -> None:
    if not _client:
        return
    _safe(lambda: _client.set(f"{PREFIX}:cache:{key}", json.dumps(value), ex=ttl))


# --------------------------------------------------------------------------- #
# Session store (Hash + TTL)
# --------------------------------------------------------------------------- #
def session_get(session_id: str) -> Optional[Dict]:
    if not _client:
        return None
    raw = _safe(lambda: _client.get(f"{PREFIX}:session:{session_id}"))
    return json.loads(raw) if raw else None


def session_set(session_id: str, state: Dict, ttl: int = 3600) -> None:
    if not _client:
        return
    _safe(lambda: _client.set(f"{PREFIX}:session:{session_id}", json.dumps(state), ex=ttl))


# --------------------------------------------------------------------------- #
# Audit trail (Streams)
# --------------------------------------------------------------------------- #
def audit(event: str, fields: Optional[Dict[str, Any]] = None) -> None:
    if not _client:
        return
    payload = {"event": event}
    for k, v in (fields or {}).items():
        payload[k] = v if isinstance(v, str) else json.dumps(v)
    _safe(lambda: _client.xadd(AUDIT_STREAM, payload, maxlen=1000, approximate=True))


def recent_audit(n: int = 10) -> List[Dict]:
    if not _client:
        return []
    rows = _safe(lambda: _client.xrevrange(AUDIT_STREAM, count=n), default=[]) or []
    return [{"id": rid, **fields} for rid, fields in rows]


# --------------------------------------------------------------------------- #
# Live stats (Hash counters)
# --------------------------------------------------------------------------- #
def incr_stat(field: str, amount: int = 1) -> None:
    if not _client:
        return
    _safe(lambda: _client.hincrby(STATS_KEY, field, amount))


def get_stats() -> Dict[str, int]:
    if not _client:
        return {}
    raw = _safe(lambda: _client.hgetall(STATS_KEY), default={}) or {}
    return {k: int(v) for k, v in raw.items()}
