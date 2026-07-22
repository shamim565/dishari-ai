from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.journeys import engine
from apps.navigation.views import STAGE_NAV_TARGETS

from apps.ai import registry
from apps.core.i18n import translate
from apps.journeys.services import attach_journey, create_journey, todays_flights
from apps.tickets.handoff import (
    HANDOFF_KEY,
    current_lang,
    ensure_handoff,
    hold_active,
    mark_phone_seen,
)
from apps.tickets.imaging import UnsupportedImage, normalize_ticket_image
from apps.tickets.models import TicketHandoff
from apps.tickets.qr import qr_data_uri
from apps.tickets.services import (
    ExtractionFailed,
    VisionUnavailable,
    extract_ticket_data,
    log_scan,
    match_flight,
)
from apps.tickets.ticketdata import ticket_data

ERROR_KEYS = {
    "bad_file": "err_bad_file",
    "no_flight": "err_no_flight",
    "not_dac": "err_not_dac",
    "ai": "err_ai",
    "extract": "err_generic",
}


def ticket_context(request):
    handoff = ensure_handoff(request)
    handoff_url = settings.BASE_URL.rstrip("/") + reverse("ticket_phone", args=[handoff.token])
    error = request.GET.get("e")
    return {
        "error_message": translate(ERROR_KEYS[error], current_lang(request)) if error in ERROR_KEYS else None,
        "ai_available": registry.vision_available(),
        "provider_label": (registry.vision_setup() or {}).get("label", ""),
        "flights": todays_flights(),
        "handoff": handoff,
        "handoff_url": handoff_url,
        "handoff_qr": qr_data_uri(handoff_url),
        "handoff_hold": hold_active(handoff),
    }


def ticket_upload(request):
    return redirect(f"{reverse('home')}?view=ticket")


def _journey_panel_fragment(request, journey):
    action = engine.next_action(journey)
    context = {
        "journey": journey,
        "flight": journey.flight,
        "action": action,
        "countdowns": engine.countdowns(journey),
        "timeline": engine.timeline(journey),
        "walk_minutes": engine.WALK_TO_GATE_MINUTES,
        "nav_target": action.get("nav_target") or STAGE_NAV_TARGETS.get(journey.stage),
    }
    response = render(request, "partials/_panel_journey.html", context)
    response["HX-Push-Url"] = "/?view=journey"
    return response


def _ticket_panel_fragment(request, error_code=None):
    context = ticket_context(request)
    if error_code in ERROR_KEYS:
        context["error_message"] = translate(ERROR_KEYS[error_code], current_lang(request))
    response = render(request, "partials/_panel_ticket.html", context)
    push = "/?view=ticket" + (f"&e={error_code}" if error_code in ERROR_KEYS else "")
    response["HX-Push-Url"] = push
    return response


def _create_journey(*, extraction, flight, source, lang):
    return create_journey(
        flight=flight,
        passenger_name=(extraction.get("passenger_name") or "").strip() or "Passenger",
        source=source,
        lang=lang,
        seat=(extraction.get("seat") or "").strip(),
        pnr=(extraction.get("pnr") or "").strip(),
        cabin=(extraction.get("cabin") or "").strip(),
        extraction=extraction,
    )


def _finish_scan(request, *, extraction, flight, source):
    journey = _create_journey(extraction=extraction, flight=flight, source=source, lang=current_lang(request))
    attach_journey(request, journey)
    request.session.pop(HANDOFF_KEY, None)
    if request.headers.get("HX-Request"):
        return _journey_panel_fragment(request, journey)
    return redirect(f"{reverse('home')}?view=journey")


def _ticket_error(request, code):
    if request.headers.get("HX-Request"):
        return _ticket_panel_fragment(request, code)
    return redirect(f"{reverse('home')}?view=ticket&e={code}")


def _process_upload(raw):
    """Shared extraction pipeline for kiosk and phone uploads.

    Returns ``(extraction, flight, error_code)`` — exactly one of flight /
    error_code is set.  Every attempt is logged to TicketScan.
    """
    try:
        image_bytes, mime_type = normalize_ticket_image(raw)
    except UnsupportedImage:
        log_scan(source="upload", success=False, error_code="bad_file")
        return None, None, "bad_file"

    if not registry.vision_available():
        log_scan(source="upload", success=False, error_code="ai_unavailable")
        return None, None, "ai"

    try:
        extraction, setup = extract_ticket_data(image_bytes, mime_type)
    except VisionUnavailable:
        log_scan(source="upload", success=False, error_code="ai_unavailable")
        return None, None, "ai"
    except ExtractionFailed:
        log_scan(source="upload", success=False, error_code="extract_failed")
        return None, None, "extract"

    flight, error_code = match_flight(extraction)
    if not flight:
        log_scan(source="upload", success=False, error_code=error_code, extraction=extraction, setup=setup)
        return None, None, "not_dac" if error_code == "err_not_dac" else "no_flight"

    log_scan(source="upload", success=True, extraction=extraction, flight=flight, setup=setup)
    return extraction, flight, None


@require_POST
def ticket_scan(request):
    upload = request.FILES.get("ticket_image")
    if not upload:
        return _ticket_error(request, "bad_file")

    extraction, flight, code = _process_upload(upload.read())
    if code:
        return _ticket_error(request, code)
    return _finish_scan(request, extraction=extraction, flight=flight, source="upload")


def ticket_demo(request):
    return redirect(f"{reverse('home')}?view=ticket")


@require_POST
def ticket_demo_pick(request, pk):
    flights = list(todays_flights())
    flight = next((f for f in flights if f.pk == pk), None)
    if not flight:
        return redirect(f"{reverse('home')}?view=ticket")
    index = next((i for i, f in enumerate(flights) if f.pk == pk), 0)
    data = ticket_data(flight, index)
    log_scan(source="demo", success=True, flight=flight)
    extraction = {
        "passenger_name": data["name_display"],
        "airline_code": flight.airline.code,
        "flight_number": flight.number,
        "origin_code": flight.origin.code,
        "destination_code": flight.destination.code,
        "seat": data["seat"],
        "pnr": data["pnr"],
    }
    return _finish_scan(request, extraction=extraction, flight=flight, source="demo")


def ticket_verified(request):
    return redirect(f"{reverse('home')}?view=journey")


# --------------------------------------------------------------------------- #
# Kiosk ⇄ phone handoff
# --------------------------------------------------------------------------- #


def _kiosk_handoff_or_404(request, token):
    if request.session.get(HANDOFF_KEY) != token:
        raise Http404
    handoff = TicketHandoff.objects.filter(token=token).first()
    if not handoff:
        raise Http404
    return handoff


def ticket_handoff_status(request, token):
    """Polled by the kiosk panel every few seconds.
