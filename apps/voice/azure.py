import hashlib
import os
from pathlib import Path
from xml.sax.saxutils import escape

import httpx
from django.conf import settings

AZURE_VOICES = {
    "bn": "bn-BD-NabanitaNeural",
    "en": "en-US-AriaNeural",
}

AZURE_LOCALES = {
    "bn": "bn-BD",
    "en": "en-US",
}

# Azure STT has no bn-BD locale — bn-IN is the closest Bengali speech model.
AZURE_STT_LOCALES = {
    "bn": "bn-IN",
    "en": "en-US",
}

TTS_TIMEOUT = 20.0
STT_TIMEOUT = 30.0


def azure_key():
    return (os.getenv("AZURE_SPEECH_KEY") or "").strip()


def azure_region():
    return (os.getenv("AZURE_SPEECH_REGION") or "southeastasia").strip()


def azure_configured():
    return bool(azure_key())


def cache_dir():
    path = Path(settings.MEDIA_ROOT) / "tts_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_key(text, voice):
    digest = hashlib.sha256(f"{voice}:{text}".encode("utf-8")).hexdigest()[:32]
    return digest


def synthesize(text, lang):
    voice = AZURE_VOICES.get(lang, AZURE_VOICES["en"])
    locale = AZURE_LOCALES.get(lang, "en-US")
    cache_path = cache_dir() / f"{cache_key(text, voice)}.mp3"
    if cache_path.exists():
        return cache_path.read_bytes(), voice

    ssml = (
        f"<speak version='1.0' xml:lang='{locale}'>"
        f"<voice name='{voice}'>{escape(text)}</voice></speak>"
    )
    url = f"https://{azure_region()}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": azure_key(),
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
        "User-Agent": "dishari-demo",
    }
    with httpx.Client(timeout=TTS_TIMEOUT) as client:
        response = client.post(url, headers=headers, content=ssml.encode("utf-8"))
    response.raise_for_status()
    audio = response.content
    cache_path.write_bytes(audio)
    return audio, voice


def recognize_wav(wav_bytes, lang):
    locale = AZURE_STT_LOCALES.get(lang, "en-US")
    url = (
        f"https://{azure_region()}.stt.speech.microsoft.com/speech/recognition/"
        f"conversation/cognitiveservices/v1?language={locale}"
