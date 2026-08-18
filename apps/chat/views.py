import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST

from apps.ai import registry
from apps.ai.client import build_client
from apps.chat.demo import demo_reply
from apps.chat.emergency import detect_emergency
from apps.chat.models import ChatMessage
from apps.chat.prompts import chat_messages
from apps.core.i18n import DEFAULT_LANG
from apps.journeys.services import get_active_journey

MAX_MESSAGE_CHARS = 500


def _lang(request):
    lang = request.session.get("lang", DEFAULT_LANG)
    return lang if lang in ("bn", "en") else DEFAULT_LANG


def _session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


def _history_qs(request, journey):
    if journey is not None:
        return ChatMessage.objects.filter(journey=journey)
    return ChatMessage.objects.filter(journey__isnull=True, session_key=_session_key(request))


def _store_message(request, journey, **fields):
    return ChatMessage.objects.create(
        journey=journey,
        session_key="" if journey is not None else _session_key(request),
        **fields,
    )


def chat_context(request):
    lang = _lang(request)
    return {
        "chat_available": registry.chat_setup() is not None,
        "stt_lang": "bn-BD" if lang == "bn" else "en-US",
    }


def _sse(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_text(text, size=7):
    words = text.split(" ")
    buffer = ""
    for word in words:
        candidate = f"{buffer} {word}".strip()
        if len(candidate) >= size:
            yield candidate + " "
            buffer = ""
        else:
            buffer = candidate
    if buffer:
        yield buffer


def _llm_stream(setup, messages):
    client = build_client(setup)
    response = client.chat.completions.create(
        model=setup["model"],
        messages=messages,
        temperature=0.3,
        stream=True,
    )
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta
