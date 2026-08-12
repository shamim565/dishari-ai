from django.shortcuts import redirect
from django.urls import reverse

from apps.journeys.models import JourneySession
from apps.journeys.services import get_active_journey
from apps.navigation.engine import LOCATION_INDEX, find_route, refresh_location_index
from apps.navigation.models import Location

LOCATION_KEY = "location_code"

STAGE_NAV_TARGETS = {
    JourneySession.STAGE_ENTERED: "checkin",
    JourneySession.STAGE_CHECK_IN: "immigration",
    JourneySession.STAGE_IMMIGRATION: "security",
    JourneySession.STAGE_SECURITY: "airside",
    JourneySession.STAGE_AIRSIDE: "gate",
    JourneySession.STAGE_GATE: "gate",
}


def get_current_location(request):
    code = request.session.get(LOCATION_KEY)
    if not code:
        return None
    return Location.objects.filter(code=code).first()


def site_locations():
    return Location.objects.filter(label_visible=True).order_by("kind", "code")


def _by_code(code):
    return Location.objects.filter(code=code).first()


def resolve_target(param, journey):
    if not param:
        return None, None
    value = param.strip().lower()
    if value == "checkin" and journey:
        block = (journey.flight.checkin_block or "B").upper()
        return _by_code(f"BLK_{block}") or _by_code("BLK_B"), None
    if value == "immigration":
        return _by_code("IMM"), None
    if value == "security":
        return _by_code("SEC"), None
    if value == "airside":
        return _by_code("AIR"), None
    if value == "gate":
        if journey and journey.flight.gate:
            return _by_code(f"GATE{journey.flight.gate}") or _by_code("AIR"), None
        return _by_code("AIR"), "gate_pending"
    return _by_code(param), None


def stage_nav_target(journey):
    if not journey:
        return None
    return STAGE_NAV_TARGETS.get(journey.stage)


def map_context(request):
    scanned = request.GET.get("scanned", "")
    return {
        "locations": site_locations(),
        "current": get_current_location(request),
        "unknown": request.GET.get("unknown", ""),
        "scanned_location": Location.objects.filter(code=scanned).first() if scanned else None,
    }


def navigate_context(request, journey):
    current = get_current_location(request)
    to_param = request.GET.get("to", "")
    target, notice = resolve_target(to_param, journey)

    if not target and not to_param and journey:
        target, notice = resolve_target(stage_nav_target(journey), journey)

    route = None
    assumed_from_entry = False
    if target:
        origin = current
        if not origin:
            origin = _by_code("ENTRY")
            assumed_from_entry = True
        route = find_route(origin, target)

    return {
        "locations": site_locations(),
        "current": current,
        "target": target,
        "route": route,
        "notice": notice,
        "assumed_from_entry": assumed_from_entry,
    }


def lost_context(request, journey):
    current = get_current_location(request)
    target = None
    route = None
    step_index = 0
    if journey:
        target, _notice = resolve_target(stage_nav_target(journey), journey)
        origin = current or _by_code("ENTRY")
        route = find_route(origin, target)
    if route and route.steps:
        try:
            step_index = max(0, min(int(request.GET.get("step", 0)), len(route.steps)))
        except ValueError:
            step_index = 0
    step = route.steps[step_index] if route and step_index < len(route.steps) else None
    step_location = None
    if step:
        refresh_location_index()
        step_location = LOCATION_INDEX.get(step.to_code)
    arrived = bool(route and route.steps and step_index >= len(route.steps))
    return {
        "current": current,
        "route": route,
        "step": step,
        "step_location": step_location,
        "step_index": step_index,
        "arrived": arrived,
        "locations": site_locations(),
    }


def airport_map(request):
    return redirect(f"{reverse('home')}?view=map")


def navigate(request):
    to_param = request.GET.get("to", "")
    return redirect(f"{reverse('home')}?view=navigate&to={to_param}")


def scan_marker(request, code):
    location = Location.objects.filter(qr_code__iexact=code).first()
    if not location:
        return redirect(f"{reverse('home')}?view=map&unknown={code}")
    request.session[LOCATION_KEY] = location.code
    return redirect(f"{reverse('home')}?view=map&scanned={location.code}")


def lost(request):
    step_param = request.GET.get("step", "")
    return redirect(f"{reverse('home')}?view=lost&step={step_param}")
