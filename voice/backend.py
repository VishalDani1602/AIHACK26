"""CareLoop voice web app backend (Deepgram STT + TTS bridge).

Pipeline per turn:
  browser mic audio --> Deepgram STT (Nova-3, multilingual)
                    --> CareLoop orchestrator (agent mesh via REST, or local fallback)
                    --> Deepgram TTS (Aura-2) --> audio back to the browser

Run:
  ./venv/bin/uvicorn voice.backend:app --port 8080 --reload
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Dict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agents.common import store
from agents.common.orchestration import LocalSpecialists, handle_turn, new_state

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "").strip()
DG_STT_MODEL = os.getenv("DEEPGRAM_STT_MODEL", "nova-3")
DG_TTS_MODEL = os.getenv("DEEPGRAM_TTS_MODEL", "aura-2-thalia-en")
DG_DEFAULT_LANG = os.getenv("DEEPGRAM_STT_LANG", "multi")  # Nova-3 multilingual code-switching
ORCH_URL = os.getenv("ORCHESTRATOR_REST_URL", "http://127.0.0.1:8000/voice")

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="CareLoop Voice")

# In-memory session state for the local fallback path (used if the agent mesh is down).
_LOCAL_SESSIONS: Dict[str, dict] = {}
_LOCAL = LocalSpecialists()

DG_LISTEN = "https://api.deepgram.com/v1/listen"
DG_SPEAK = "https://api.deepgram.com/v1/speak"

_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⌀-⏿]"
)


def speechify(text: str) -> str:
    """Strip markdown/emoji so the TTS reads cleanly."""
    text = _EMOJI.sub("", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # bold
    text = text.replace("*", "").replace("#", "").replace("`", "")
    text = re.sub(r"\s*\n\s*", ". ", text)         # newlines -> sentence breaks
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    return text.strip()


async def deepgram_stt(audio: bytes, content_type: str, language: str) -> str:
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY not set")
    params = {"model": DG_STT_MODEL, "smart_format": "true", "punctuate": "true"}
    if language:
        params["language"] = language
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            DG_LISTEN, params=params,
            headers={"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": content_type or "audio/webm"},
            content=audio,
        )
        r.raise_for_status()
        data = r.json()
    try:
        return data["results"]["channels"][0]["alternatives"][0]["transcript"].strip()
    except (KeyError, IndexError):
        return ""


async def deepgram_tts(text: str) -> bytes:
    if not DEEPGRAM_API_KEY:
        raise RuntimeError("DEEPGRAM_API_KEY not set")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            DG_SPEAK, params={"model": DG_TTS_MODEL},
            headers={"Authorization": f"Token {DEEPGRAM_API_KEY}", "Content-Type": "application/json"},
            json={"text": text[:1900]},  # speak endpoint input cap safety
        )
        r.raise_for_status()
        return r.content


async def run_orchestrator(session_id: str, text: str) -> dict:
    """Route a turn through the agent mesh (REST); fall back to local orchestration."""
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(ORCH_URL, json={"session_id": session_id, "text": text})
            r.raise_for_status()
            d = r.json()
            return {"reply": d.get("reply", ""), "stage": d.get("stage", ""),
                    "emergency": bool(d.get("emergency", False)), "via": "agent-mesh"}
    except Exception:
        state = store.session_get(session_id) or _LOCAL_SESSIONS.get(session_id) or new_state()
        state["session_id"] = session_id
        out = await handle_turn(state, text, _LOCAL)
        _LOCAL_SESSIONS[session_id] = state
        store.session_set(session_id, state)
        return {**out, "via": "local-fallback"}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"deepgram_key": bool(DEEPGRAM_API_KEY), "orchestrator_url": ORCH_URL,
            "stt_model": DG_STT_MODEL, "tts_model": DG_TTS_MODEL, "redis": store.enabled()}


@app.get("/api/stats")
async def stats():
    """Live Redis-backed counters + recent audit-trail events (beyond caching)."""
    return {"redis": store.enabled(), "stats": store.get_stats(), "recent": store.recent_audit(8)}


@app.post("/api/text")
async def api_text(payload: dict):
    """Typed-input turn (no audio). Returns reply text + spoken audio."""
    session_id = payload.get("session_id", "web")
    text = (payload.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "empty text"}, status_code=400)
    result = await run_orchestrator(session_id, text)
    audio_b64 = await _tts_b64(result["reply"])
    return {"transcript": text, **result, "audio": audio_b64}


@app.post("/api/converse")
async def api_converse(request: Request):
    """Audio-input turn: STT -> orchestrator -> TTS. Audio is the raw request body."""
    session_id = request.query_params.get("session_id", "web")
    language = request.query_params.get("language", DG_DEFAULT_LANG)
    content_type = request.headers.get("content-type", "audio/webm")
    audio = await request.body()
    if not audio:
        return JSONResponse({"error": "no audio"}, status_code=400)
    try:
        transcript = await deepgram_stt(audio, content_type, language)
    except Exception as exc:
        return JSONResponse({"error": f"STT failed: {exc}"}, status_code=502)
    if not transcript:
        return {"transcript": "", "reply": "Sorry, I didn't catch that. Could you say it again?",
                "stage": "collecting", "emergency": False, "audio": ""}
    result = await run_orchestrator(session_id, transcript)
    audio_b64 = await _tts_b64(result["reply"])
    return {"transcript": transcript, **result, "audio": audio_b64}


async def _tts_b64(reply: str) -> str:
    try:
        audio_bytes = await deepgram_tts(speechify(reply))
        return base64.b64encode(audio_bytes).decode("ascii")
    except Exception:
        return ""  # UI still shows text if TTS fails


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
