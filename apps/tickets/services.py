import base64
import json
import re
from datetime import timedelta

from django.utils import timezone

from apps.ai.client import build_client
from apps.ai import registry
from apps.ai.prompts import ticket_messages
from apps.flights.models import Flight
from apps.tickets.models import TicketScan


class VisionUnavailable(Exception):
    pass


class ExtractionFailed(Exception):
    pass


def extract_ticket_data(image_bytes, mime_type):
    setup = registry.vision_setup()
    if not setup:
        raise VisionUnavailable
    data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    client = build_client(setup)
    try:
        response = client.chat.completions.create(
            model=setup["model"],
            temperature=0,
            messages=ticket_messages(data_uri),
        )
    except Exception as exc:
        raise ExtractionFailed(str(exc)) from exc
    text = (response.choices[0].message.content or "").strip()
    return parse_json_object(text), setup


def parse_json_object(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ExtractionFailed("model returned invalid JSON")


def normalize_flight_number(raw_number, airline_code):
    number = re.sub(r"[^A-Za-z0-9]", "", str(raw_number or "")).upper()
    code = re.sub(r"[^A-Za-z0-9]", "", str(airline_code or "")).upper()
    if number.isdigit() and code:
        number = f"{code}{number}"
    return number


def match_flight(data):
    number = normalize_flight_number(data.get("flight_number"), data.get("airline_code"))
    if not number:
        return None, "err_no_flight"

    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    flight = (
        Flight.objects.select_related("airline", "origin", "destination")
        .filter(number=number, date__in=[today, tomorrow])
        .first()
    )
    if not flight:
        return None, "err_no_flight"

    origin = str(data.get("origin_code") or "").strip().upper()
    if origin and origin != flight.origin.code:
        return None, "err_not_dac"

    return flight, None


def log_scan(*, source, success, error_code="", extraction=None, flight=None, setup=None):
    return TicketScan.objects.create(
        source=source,
        success=success,
        error_code=error_code,
        raw_extraction=extraction or {},
        flight=flight,
        provider=(setup or {}).get("provider", ""),
        model=(setup or {}).get("model", ""),
    )
