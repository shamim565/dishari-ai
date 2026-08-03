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
