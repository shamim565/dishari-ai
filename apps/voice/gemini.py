import base64
import hashlib
import os
from pathlib import Path

import httpx
from django.conf import settings

GEMINI_TTS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GEMINI_TTS_STYLE = "warm and friendly, calm and clear"
TTS_TIMEOUT = 60.0


def gemini_key():
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def gemini_configured():
    return bool(gemini_key())


def tts_model():
    return (os.getenv("GEMINI_TTS_MODEL") or "gemini-3.8-flash-tts").strip()


def tts_voice(lang):
    env_key = "GEMINI_TTS_VOICE_EN" if lang == "en" else "GEMINI_TTS_VOICE"
    return (os.getenv(env_key) or os.getenv("GEMINI_TTS_VOICE") or "Kore").strip()


def cache_dir():
    path = Path(settings.MEDIA_ROOT) / "tts_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_key(text, voice):
    digest = hashlib.sha256(f"gemini:{voice}:{text}".encode("utf-8")).hexdigest()[:32]
    return digest


def synthesize(text, lang):
    voice = tts_voice(lang)
    cache_path = cache_dir() / f"{cache_key(text, voice)}.wav"
    if cache_path.exists():
        return cache_path.read_bytes(), voice

    payload = {
        "model": tts_model(),
        "input": [
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                        "annotations": [
                            {"type": "speech_metadata", "style": GEMINI_TTS_STYLE}
                        ],
                    }
                ],
            }
        ],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    headers = {"x-goog-api-key": gemini_key(), "Content-Type": "application/json"}
    with httpx.Client(timeout=TTS_TIMEOUT) as client:
        response = client.post(GEMINI_TTS_URL, headers=headers, json=payload)
    response.raise_for_status()
    audio = _extract_audio(response.json())
    cache_path.write_bytes(audio)
    return audio, voice


def _extract_audio(payload):
    for step in payload.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for content in step.get("content", []):
            if content.get("type") == "audio" and content.get("data"):
                return base64.b64decode(content["data"])
    raise ValueError("gemini_tts_no_audio")
