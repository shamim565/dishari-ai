from collections import Counter

from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.chat.demo import TOPIC_LABELS, detect_topic
from apps.chat.models import ChatMessage
from apps.core.i18n import DEFAULT_LANG
from apps.core.times import format_clock
from apps.flights.models import Flight
from apps.journeys.models import JourneySession
from apps.journeys.services import get_active_journey, todays_flights
from apps.notifications.engine import create_event
from apps.notifications.models import FlightEvent
from apps.tickets.models import TicketScan


def _lang(request):
    lang = request.session.get("lang", DEFAULT_LANG)
    return lang if lang in ("bn", "en") else DEFAULT_LANG


def notifications_context(request):
    journey = get_active_journey(request)
    events = FlightEvent.objects.filter(flight=journey.flight)[:30] if journey else FlightEvent.objects.none()
    return {"journey": journey, "events": events}


def notifications_page(request):
    return redirect(f"{reverse('home')}?view=notifications")


def api_events(request):
    journey = get_active_journey(request)
    if request.GET.get("peek"):
        latest = FlightEvent.objects.order_by("-id").values_list("id", flat=True).first() or 0
        return JsonResponse({"latest": latest})

    try:
        after = int(request.GET.get("after", 0))
    except (TypeError, ValueError):
        after = 0

    events = FlightEvent.objects.filter(id__gt=after)
    events = events.filter(flight=journey.flight) if journey else events.none()
    lang = _lang(request)
    payload = [
        {
            "id": event.id,
            "kind": event.kind,
            "priority": event.priority,
            "message": event.message(lang),
            "time": format_clock(event.created_at, lang),
            "speak": True,
        }
        for event in events.order_by("id")[:10]
    ]
    return JsonResponse({"events": payload})


def ops_guard(request):
    if not request.session.get("ops_ok"):
        return redirect("ops_login")
    return None


def ops_login(request):
    if request.method == "POST":
        if (request.POST.get("pin") or "").strip() == str(settings.OPS_PIN):
            request.session["ops_ok"] = True
            return redirect("ops_panel")
        return render(request, "ops/login.html", {"error": True})
    return render(request, "ops/login.html", {"error": False})


def ops_logout(request):
    request.session.pop("ops_ok", None)
    return redirect("ops_login")


def ops_panel(request):
    guard = ops_guard(request)
    if guard:
        return guard
    sessions = (
        JourneySession.objects.select_related("flight", "flight__airline")
        .order_by("-created_at")[:10]
    )

    user_messages = list(ChatMessage.objects.filter(role="user").values_list("content", flat=True))
    topic_counts = Counter(detect_topic(message) for message in user_messages)
    total = len(user_messages) or 1
    topics = [
        {
            "label": TOPIC_LABELS.get(key, key.title()),
            "count": count,
            "pct": round(100 * count / total),
        }
        for key, count in topic_counts.most_common(6)
    ]
    lang_counts = Counter(JourneySession.objects.values_list("lang", flat=True))

    return render(
        request,
        "ops/panel.html",
        {
            "flights": todays_flights(),
            "sessions": sessions,
            "events": FlightEvent.objects.select_related("flight")[:12],
            "stats": {
                "sessions": JourneySession.objects.count(),
                "scans": TicketScan.objects.count(),
                "messages": ChatMessage.objects.count(),
            },
            "topics": topics,
            "lang_split": {"bn": lang_counts.get("bn", 0), "en": lang_counts.get("en", 0)},
            "message_total": len(user_messages),
        },
    )


ACTION_KINDS = {
    "check-in-open": FlightEvent.KIND_CHECK_IN_OPEN,
    "counter-change": FlightEvent.KIND_COUNTER_CHANGE,
    "gate-assign": FlightEvent.KIND_GATE_ASSIGNED,
    "gate-change": FlightEvent.KIND_GATE_CHANGE,
    "boarding": FlightEvent.KIND_BOARDING,
    "final-call": FlightEvent.KIND_FINAL_CALL,
    "delay": FlightEvent.KIND_DELAY,
    "cancel": FlightEvent.KIND_CANCELLED,
}


@require_POST
def ops_action(request, pk, action):
    guard = ops_guard(request)
    if guard:
        return guard
    kind = ACTION_KINDS.get(action)
    flight = Flight.objects.filter(pk=pk).first()
    if not kind or not flight:
        messages.error(request, f"Unknown action: {action}")
        return redirect("ops_panel")

    if kind == FlightEvent.KIND_COUNTER_CHANGE:
        create_event(
            flight,
            kind,
            counters=(request.POST.get("counters") or "").strip(),
            block=(request.POST.get("block") or "").strip().upper(),
        )
    elif kind in (FlightEvent.KIND_GATE_ASSIGNED, FlightEvent.KIND_GATE_CHANGE):
        create_event(flight, kind, gate=(request.POST.get("gate") or "").strip().upper())
    elif kind == FlightEvent.KIND_DELAY:
        try:
            minutes = max(5, min(int(request.POST.get("minutes", 60)), 24 * 60))
        except (TypeError, ValueError):
            minutes = 60
        create_event(flight, kind, delay_minutes=minutes)
    else:
        create_event(flight, kind)

    messages.success(request, f"{flight.number}: {kind} event sent.")
    return redirect("ops_panel")


@require_POST
def ops_reset(request):
    guard = ops_guard(request)
    if guard:
        return guard
    call_command("seed_demo")
    call_command("seed_nav")
    messages.success(request, "Demo data reset (flights + layout re-seeded, sessions cleared).")
    return redirect("ops_panel")


@require_POST
def ops_clear_events(request):
    guard = ops_guard(request)
    if guard:
        return guard
    FlightEvent.objects.all().delete()
    messages.success(request, "All flight events cleared.")
    return redirect("ops_panel")
