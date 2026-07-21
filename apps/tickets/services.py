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
