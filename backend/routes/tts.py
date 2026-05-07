"""
Text-to-Speech route.

Priority:
  1. ElevenLabs API  (if ELEVENLABS_API_KEY is set) — best quality, very natural
  2. OpenAI TTS API  (if OPENAI_TTS_API_KEY is set) — excellent quality
  3. gTTS (Google TTS via network)                  — good quality, free
  4. Returns 503 so the frontend falls back to browser speechSynthesis

Endpoint:  POST /api/tts
Body:      { "text": "...", "voice": "" }   (voice overrides env default)
Response:  audio/mpeg  (MP3 bytes)
"""

import io
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

# ElevenLabs voice IDs for common presets
# Full list: https://api.elevenlabs.io/v1/voices
ELEVENLABS_VOICE_MAP = {
    "nova":        "EXAVITQu4vr4xnSDxMaL",  # Sarah  — warm, clear, professional
    "alloy":       "pNInz6obpgDQGcFmaJgB",  # Adam   — neutral, authoritative
    "echo":        "VR6AewLTigWG4xSOukaG",  # Arnold — deep, confident
    "shimmer":     "21m00Tcm4TlvDq8ikWAM",  # Rachel — friendly, conversational
    "onyx":        "yoZ06aMxZJJ28mfd3POQ",  # Sam    — deep, steady
    "fable":       "AZnzlk1XvdvUeBnXmlld",  # Domi   — expressive
    "interviewer": "EXAVITQu4vr4xnSDxMaL",  # Sarah  — default interviewer voice
}


class TTSRequest(BaseModel):
    text: str
    voice: str = ""          # overrides env default when provided


def _elevenlabs_tts(text: str, voice_hint: str) -> bytes:
    """Call ElevenLabs TTS and return raw MP3 bytes."""
    import httpx

    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    # Resolve voice: explicit ID > mapped alias > env default > Sarah
    env_voice = os.getenv("TTS_VOICE", "nova")
    hint = voice_hint or env_voice
    voice_id = (
        hint if len(hint) > 20            # already a raw ElevenLabs voice ID
        else ELEVENLABS_VOICE_MAP.get(hint, ELEVENLABS_VOICE_MAP["nova"])
    )

    payload = {
        "text": text[:5000],
        "model_id": "eleven_turbo_v2_5",  # fast + high-quality
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.80,
            "style": 0.30,
            "use_speaker_boost": True,
        },
    }

    with httpx.Client(timeout=25) as client:
        resp = client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS error {resp.status_code}: {resp.text[:200]}")

    return resp.content


def _openai_tts(text: str, voice: str) -> bytes:
    """Call OpenAI TTS and return raw MP3 bytes."""
    import httpx

    api_key = os.getenv("OPENAI_TTS_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_TTS_API_KEY not set")

    effective_voice = voice or os.getenv("TTS_VOICE", "nova")

    payload = {
        "model": "tts-1",
        "input": text[:4096],
        "voice": effective_voice,
    }

    with httpx.Client(timeout=20) as client:
        resp = client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI TTS error {resp.status_code}: {resp.text[:200]}")

    return resp.content


def _gtts_tts(text: str) -> bytes:
    """Generate MP3 via gTTS (requires network; no API key needed)."""
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise RuntimeError("gTTS not installed — run: pip install gtts") from exc

    buf = io.BytesIO()
    tts = gTTS(text=text[:3000], lang="en", tld="com", slow=False)
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf.read()


@router.post("/tts")
async def synthesize(req: TTSRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text field is required")

    # 1) ElevenLabs — best quality
    if os.getenv("ELEVENLABS_API_KEY"):
        try:
            audio_bytes = _elevenlabs_tts(req.text, req.voice)
            return StreamingResponse(
                io.BytesIO(audio_bytes),
                media_type="audio/mpeg",
                headers={"X-TTS-Provider": "elevenlabs"},
            )
        except Exception as exc:
            print(f"[TTS] ElevenLabs failed ({exc}), trying OpenAI")

    # 2) OpenAI TTS
    if os.getenv("OPENAI_TTS_API_KEY"):
        try:
            audio_bytes = _openai_tts(req.text, req.voice)
            return StreamingResponse(
                io.BytesIO(audio_bytes),
                media_type="audio/mpeg",
                headers={"X-TTS-Provider": "openai"},
            )
        except Exception as exc:
            print(f"[TTS] OpenAI TTS failed ({exc}), trying gTTS")

    # 3) gTTS
    try:
        audio_bytes = _gtts_tts(req.text)
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"X-TTS-Provider": "gtts"},
        )
    except Exception as exc:
        print(f"[TTS] gTTS also failed ({exc})")

    # 4) All failed — frontend falls back to browser synthesis
    raise HTTPException(
        status_code=503,
        detail={"code": "tts_unavailable", "message": "No TTS provider available"},
    )
