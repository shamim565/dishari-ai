import datetime
import hashlib
import os

import httpx

from apps.chat.context import build_system_prompt, journey_context
from apps.voice.gemini import tts_voice

AUTH_TOKENS_URL = "https://generativelanguage.googleapis.com/v1beta/auth_tokens"
LIVE_WS_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained"
)
TOKEN_TIMEOUT = 20.0


def live_key():
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def live_configured():
    return bool(live_key())


def live_model():
    return (os.getenv("GEMINI_LIVE_MODEL") or "gemini-3.8-live").strip()


def _iso(ts):
    return ts.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def session_config(journey, request, lang):
    # Note: the current v1beta WS schema nests modalities/speech under
    # `generationConfig` (the flattened docs schema is not accepted yet).
    generation = {
        "responseModalities": ["AUDIO"],
        "speechConfig": {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": tts_voice(lang)}}
        },
    }
    if "extended-thinking" in live_model():
        generation["thinkingConfig"] = {"thinkingLevel": "low"}
    return {
        "generationConfig": generation,
        "systemInstruction": {
            "parts": [{"text": build_system_prompt(journey, request, lang)}]
        },
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
        "sessionResumption": {},
    }


def context_text(journey, request, lang):
    if journey is None:
        return ""
    return journey_context(journey, lang)


def context_hash(journey, request, lang):
    text = context_text(journey, request, lang)
    if not text:
        return "none"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def mint_token():
    # Note: `liveConnectConstraints` is documented but rejected by the current
    # v1beta auth_tokens endpoint ("Unknown name"), so we mint a plain
    # short-lived, Live-only token and send the full setup over the socket.
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "uses": 1,
        "expireTime": _iso(now + datetime.timedelta(minutes=30)),
        "newSessionExpireTime": _iso(now + datetime.timedelta(minutes=1)),
    }
    headers = {"x-goog-api-key": live_key(), "Content-Type": "application/json"}
    with httpx.Client(timeout=TOKEN_TIMEOUT) as client:
        response = client.post(AUTH_TOKENS_URL, headers=headers, json=payload)
    response.raise_for_status()
    token = (response.json().get("name") or "").strip()
    if not token:
        raise ValueError("live_token_missing")
    return token
