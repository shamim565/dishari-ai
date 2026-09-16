import os

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.core.i18n import DEFAULT_LANG
from apps.journeys.services import get_active_journey
from apps.voice import azure, gemini, live

MAX_TTS_CHARS = 600
MAX_STT_BYTES = 4 * 1024 * 1024


def _lang(request):
    source = request.POST.get("lang") or request.session.get("lang", DEFAULT_LANG)
    return source if source in ("bn", "en") else DEFAULT_LANG


def tts_provider():
    return (os.getenv("TTS_PROVIDER") or "gemini").strip().lower()


def tts_status(request):
    return JsonResponse(
        {
            "available": gemini.gemini_configured() or azure.azure_configured(),
            "provider": tts_provider(),
            "voices": {
                "gemini": {"bn": gemini.tts_voice("bn"), "en": gemini.tts_voice("en")},
                "azure": azure.AZURE_VOICES,
            },
        }
    )


@require_POST
def tts(request):
    text = (request.POST.get("text") or "").strip()[:MAX_TTS_CHARS]
    if not text:
        return JsonResponse({"detail": "empty"}, status=400)
    lang = _lang(request)

    if tts_provider() == "gemini":
        attempts = [("gemini", gemini), ("azure", azure)]
    else:
        attempts = [("azure", azure), ("gemini", gemini)]

    used = None
    audio = None
    voice = ""
    for name, module in attempts:
        if name == "gemini" and not gemini.gemini_configured():
            continue
        if name == "azure" and not azure.azure_configured():
            continue
        try:
            audio, voice = module.synthesize(text, lang)
            used = name
            break
        except Exception:
            audio = None

    if audio is None:
        if not gemini.gemini_configured() and not azure.azure_configured():
            return JsonResponse({"detail": "tts_unavailable"}, status=503)
        return JsonResponse({"detail": "tts_error"}, status=502)

    response = HttpResponse(
        audio, content_type="audio/wav" if used == "gemini" else "audio/mpeg"
    )
    response["X-Voice"] = voice
    response["X-TTS-Provider"] = used or ""
    response["Cache-Control"] = "public, max-age=86400"
    return response


@require_POST
def stt(request):
    if not azure.azure_configured():
        return JsonResponse({"detail": "stt_unavailable"}, status=503)
    upload = request.FILES.get("audio")
    if not upload:
        return JsonResponse({"detail": "empty"}, status=400)
    raw = upload.read()
    if len(raw) > MAX_STT_BYTES:
        return JsonResponse({"detail": "too_large"}, status=413)
    try:
        text = azure.recognize_wav(raw, _lang(request))
    except Exception:
        return JsonResponse({"detail": "stt_error"}, status=502)
    return JsonResponse({"text": text})


@require_POST
def live_token(request):
    if not live.live_configured():
        return JsonResponse({"detail": "live_unavailable"}, status=503)
    lang = _lang(request)
    journey = get_active_journey(request)
    try:
        token = live.mint_token()
    except Exception:
        return JsonResponse({"detail": "live_token_error"}, status=502)
    return JsonResponse(
        {
            "token": token,
            "ws_url": live.LIVE_WS_URL,
            "model": live.live_model(),
            "config": live.session_config(journey, request, lang),
            "ctx_hash": live.context_hash(journey, request, lang),
        }
    )
