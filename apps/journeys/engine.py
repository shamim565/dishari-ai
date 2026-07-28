from datetime import datetime, timedelta

from django.utils import timezone

from apps.journeys.models import JourneySession

WALK_TO_GATE_MINUTES = 12
BOARDING_LEAD_MINUTES = 45
GATE_BUFFER_MINUTES = 10

STAGE_SEQUENCE = [
    JourneySession.STAGE_ENTERED,
    JourneySession.STAGE_CHECK_IN,
    JourneySession.STAGE_IMMIGRATION,
    JourneySession.STAGE_SECURITY,
    JourneySession.STAGE_AIRSIDE,
    JourneySession.STAGE_GATE,
    JourneySession.STAGE_BOARDED,
]

TIMELINE_STEPS = [
    ("step_airport_entry", 1),
    ("step_checkin", 2),
    ("step_immigration", 3),
    ("step_security", 4),
    ("step_gate", 5),
    ("step_boarding", 6),
]


def stage_index(stage):
    try:
        return STAGE_SEQUENCE.index(stage)
    except ValueError:
        return 0


def _aware(date, time_value):
    return timezone.make_aware(datetime.combine(date, time_value), timezone.get_current_timezone())


def departure_time(journey):
    return _aware(journey.flight.date, journey.flight.effective_departure)


def boarding_time(journey):
    if journey.flight.boarding_time:
        return _aware(journey.flight.date, journey.flight.boarding_time)
    return departure_time(journey) - timedelta(minutes=BOARDING_LEAD_MINUTES)


def leave_for_gate_time(journey):
    return boarding_time(journey) - timedelta(minutes=WALK_TO_GATE_MINUTES + GATE_BUFFER_MINUTES)


def flight_missed(flight, now=None):
    """True when the flight can no longer be boarded (departed or gate closed).

    Uses the real-time-aware ``effective_status`` so stale manual statuses are
    superseded by the clock. Cancelled is handled separately in ``next_action``.
    """
    return flight.effective_status(now) in (flight.STATUS_DEPARTED, flight.STATUS_GATE_CLOSED)


def countdowns(journey):
    now = timezone.now()
    entries = [
        ("departure_label", departure_time(journey)),
        ("boarding_starts_label", boarding_time(journey)),
        ("leave_for_gate_label", leave_for_gate_time(journey)),
    ]
    return [
        {
            "key": key,
            "at": at,
            "minutes": int((at - now).total_seconds() // 60),
        }
        for key, at in entries
    ]


def timeline(journey):
    index = stage_index(journey.stage)
    items = []
    current_assigned = False
    for key, threshold in TIMELINE_STEPS:
        if index >= threshold:
            state = "done"
        elif not current_assigned:
            state = "current"
            current_assigned = True
        else:
            state = "upcoming"
        items.append({"key": key, "state": state})
    if index >= len(STAGE_SEQUENCE) - 1:
        for item in items:
            item["state"] = "done"
    return items


def next_action(journey):
    flight = journey.flight
    stage = journey.stage
    status = flight.effective_status()

    if stage == JourneySession.STAGE_BOARDED:
        return {
            "state": "done",
            "title_key": "task_boarded_title",
            "note_key": "task_boarded_note",
            "warning_key": None,
            "advance_allowed": False,
        }

    if status == flight.STATUS_CANCELLED:
        return {
            "state": "active",
            "title_key": "task_cancelled_title",
            "note_key": "task_cancelled_note",
            "warning_key": None,
            "advance_allowed": False,
            "nav_target": "INFO",
            "cancelled": True,
        }

    if status in (flight.STATUS_DEPARTED, flight.STATUS_GATE_CLOSED):
        return {
            "state": "active",
            "title_key": "task_departed_title",
            "note_key": "task_departed_note",
            "warning_key": None,
            "advance_allowed": False,
            "nav_target": "INFO",
            "missed": True,
        }

    if stage == JourneySession.STAGE_ENTERED:
        return {
            "state": "active",
            "title_key": "task_entered_title",
            "note_key": "task_entered_note",
            "warning_key": (
                "task_checkin_wait"
                if status == flight.STATUS_SCHEDULED and not flight.checkin_open
                else None
            ),
            "advance_allowed": True,
        }
    if stage == JourneySession.STAGE_CHECK_IN:
        return {
            "state": "active",
            "title_key": "task_immigration_title",
            "note_key": "task_immigration_note",
            "warning_key": None,
            "advance_allowed": True,
        }
    if stage == JourneySession.STAGE_IMMIGRATION:
        return {
            "state": "active",
            "title_key": "task_security_title",
            "note_key": "task_security_note",
            "warning_key": None,
            "advance_allowed": True,
        }
    if stage == JourneySession.STAGE_SECURITY:
        return {
            "state": "active",
            "title_key": "task_airside_title",
            "note_key": "task_airside_note",
            "warning_key": None,
            "advance_allowed": True,
        }
    if stage == JourneySession.STAGE_AIRSIDE:
        return {
            "state": "active",
            "title_key": "task_gate_title",
            "note_key": "task_gate_note",
            "warning_key": None if flight.gate else "task_gate_pending",
            "advance_allowed": True,
        }
    if stage == JourneySession.STAGE_GATE:
        boarding = status in (
            flight.STATUS_BOARDING,
            flight.STATUS_FINAL_CALL,
        )
        return {
            "state": "active",
            "title_key": "task_boarding_title" if boarding else "task_gate_wait_title",
            "note_key": "task_boarding_note" if boarding else "task_gate_wait_note",
            "warning_key": None,
            "advance_allowed": True,
        }
    return {
        "state": "done",
        "title_key": "task_boarded_title",
        "note_key": "task_boarded_note",
        "warning_key": None,
        "advance_allowed": False,
    }
