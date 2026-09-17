from django.shortcuts import redirect, render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

from apps.chat.views import chat_context
from apps.journeys import engine
from apps.journeys.services import attach_journey, detach_journey, get_active_journey
from apps.journeys.views import arrival_context
from apps.navigation.views import lost_context, map_context, navigate_context, STAGE_NAV_TARGETS
from apps.notifications.views import notifications_context
from apps.tickets.handoff import get_ready_handoff
from apps.tickets.views import ticket_context
from apps.voice import live as live_api

VALID_VIEWS = ("ticket", "journey", "map", "navigate", "lost", "arrival", "notifications")


def _default_view(journey):
    return "journey" if journey else "ticket"


def journey_panel_context(journey):
    action = engine.next_action(journey)
    return {
        "journey": journey,
        "flight": journey.flight,
        "action": action,
        "countdowns": engine.countdowns(journey),
        "timeline": engine.timeline(journey),
        "walk_minutes": engine.WALK_TO_GATE_MINUTES,
        "nav_target": action.get("nav_target") or STAGE_NAV_TARGETS.get(journey.stage),
    }


def panel_context(request, journey, view):
    context = {"journey": journey}
    if view == "journey":
        context.update(journey_panel_context(journey))
    elif view == "ticket":
        context.update(ticket_context(request))
    elif view == "map":
        context.update(map_context(request))
    elif view == "navigate":
        context.update(navigate_context(request, journey))
    elif view == "lost":
        context.update(lost_context(request, journey))
    elif view == "arrival":
        context.update(arrival_context(request))
    elif view == "notifications":
        context.update(notifications_context(request))
    return context


def _voice_mode(request):
    mode = (request.GET.get("voice") or "live").strip().lower()
    return "tts" if mode == "tts" else "live"


@xframe_options_exempt
def assistant(request):
    mode = _voice_mode(request)
    live_ok = live_api.live_configured()
    if mode == "live" and not live_ok:
        mode = "tts"
    context = chat_context(request)
    context.update(
        {
            "voice_mode": mode,
            "live_available": live_ok,
            "live_model": live_api.live_model(),
            "live_fallback_notice": request.GET.get("fallback") == "1",
        }
    )
    return render(request, "assistant/shell.html", context)


def home(request):
    journey = get_active_journey(request)
    view = request.GET.get("view") or _default_view(journey)
    if view not in VALID_VIEWS:
        view = _default_view(journey)
    if view == "journey" and not journey:
        view = "ticket"

    # Phone finished an upload but the kiosk poll has not run yet — adopt it
    # here so navigating around the dashboard cannot lose the finished scan.
    if view == "ticket":
        handoff = get_ready_handoff(request)
        if handoff:
            attach_journey(request, handoff.journey)
            journey = handoff.journey
            view = "journey"

    context = panel_context(request, journey, view)

    if request.headers.get("HX-Request"):
        return render(request, f"partials/_panel_{view}.html", context)

    context.update({"journey": journey, "view": view})
    return render(request, "portal/home.html", context)


@require_POST
def session_end(request):
    detach_journey(request)
    request.session.flush()
    return redirect("home")
