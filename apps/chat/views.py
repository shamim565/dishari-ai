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


@require_POST
def chat_send(request):
    message = (request.POST.get("message") or "").strip()[:MAX_MESSAGE_CHARS]
    if not message:
        return JsonResponse({"detail": "empty"}, status=400)

    lang = _lang(request)
    journey = get_active_journey(request)
    setup = registry.chat_setup()

    _store_message(
        request,
        journey,
        role="user",
        content=message,
        lang=lang,
        source="llm" if setup else "demo",
    )

    def stream():
        full = []
        source = "llm"
        pending_events = []
        try:
            emergency = detect_emergency(message, lang)
            if emergency:
                source = "demo"
                pending_events.append(emergency["event"])
                iterator = _chunk_text(emergency["text"])
            elif setup:
                history = list(
                    _history_qs(request, journey).order_by("-created_at")[:10]
                )[::-1]
                messages = chat_messages(journey, request, lang, history[:-1], message)
                iterator = _llm_stream(setup, messages)
            else:
                source = "demo"
                reply = demo_reply(message, journey, request, lang)
                pending_events.extend(reply["events"])
                iterator = _chunk_text(reply["text"])
            for delta in iterator:
                full.append(delta)
                yield _sse({"delta": delta})
            for event in pending_events:
                yield _sse(event)
        except Exception:
            fallback = {
                "bn": "দুঃখিত, এই মুহূর্তে উত্তর দিতে পারছি না। আবার চেষ্টা করুন বা ইনফরমেশন ডেস্কে জিজ্ঞেস করুন।",
                "en": "Sorry, I cannot answer right now. Please try again or ask the information desk.",
            }[lang]
            full = [fallback]
            source = "demo"
            yield _sse({"delta": fallback})
        finally:
            text = "".join(full).strip()
            saved = _store_message(
                request, journey, role="assistant", content=text, lang=lang, source=source
            )
            yield _sse({"done": True, "message_id": saved.pk})

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@require_POST
def live_log(request):
    input_text = (request.POST.get("input") or "").strip()[:MAX_MESSAGE_CHARS]
    output_text = (request.POST.get("output") or "").strip()[:2000]
    if not input_text and not output_text:
        return JsonResponse({"detail": "empty"}, status=400)

    lang = _lang(request)
    journey = get_active_journey(request)
    if input_text:
        _store_message(request, journey, role="user", content=input_text, lang=lang, source="live")
    if output_text:
        _store_message(
            request, journey, role="assistant", content=output_text, lang=lang, source="live"
        )

    payload = {"stored": True}
    emergency = detect_emergency(input_text, lang) if input_text else None
    if emergency:
        payload["event"] = emergency["event"]
    return JsonResponse(payload)
