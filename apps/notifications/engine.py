from datetime import datetime, timedelta

from apps.core.times import format_clock
from apps.flights.models import Flight
from apps.notifications.models import FlightEvent


def _fmt_time(value, lang):
    return format_clock(value, lang) if value else ""


def _fmt_delta(minutes):
    hours, mins = divmod(minutes, 60)
    parts_bn, parts_en = [], []
    if hours:
        parts_bn.append(f"{hours} ঘণ্টা")
        parts_en.append(f"{hours}h")
    if mins:
        parts_bn.append(f"{mins} মিনিট")
        parts_en.append(f"{mins}m")
    return " ".join(parts_bn), " ".join(parts_en)


def create_event(flight, kind, *, counters="", block="", gate="", delay_minutes=0):
    priority = FlightEvent.PRIORITY_URGENT if kind in FlightEvent.URGENT_KINDS else FlightEvent.PRIORITY_NORMAL
    update_fields = []

    if kind == FlightEvent.KIND_CHECK_IN_OPEN:
        flight.checkin_open = True
        flight.status = Flight.STATUS_CHECK_IN_OPEN
        update_fields += ["checkin_open", "status"]
        counter_text_bn = flight.checkin_counters or "চেক-ইন কাউন্টার"
        counter_text_en = flight.checkin_counters or "the check-in counters"
        block_bn = f", ব্লক {flight.checkin_block}" if flight.checkin_block else ""
        block_en = f", Block {flight.checkin_block}" if flight.checkin_block else ""
        messages = (
            f"আপনার ফ্লাইটের চেক-ইন শুরু হয়েছে। এখন {counter_text_bn}{block_bn}-এ যান।",
            f"Check-in has started for your flight. Go to {counter_text_en}{block_en} now.",
        )
    elif kind == FlightEvent.KIND_COUNTER_CHANGE:
        if counters:
            flight.checkin_counters = counters
            update_fields.append("checkin_counters")
        if block:
            flight.checkin_block = block
            update_fields.append("checkin_block")
        messages = (
            f"চেক-ইন কাউন্টার পরিবর্তন হয়েছে। এখন কাউন্টার {flight.checkin_counters}, ব্লক {flight.checkin_block}।",
            f"Your check-in counters have changed. They are now {flight.checkin_counters}, Block {flight.checkin_block}.",
        )
    elif kind == FlightEvent.KIND_GATE_ASSIGNED:
        flight.gate = gate or flight.gate
        update_fields.append("gate")
        messages = (
            f"আপনার বোর্ডিং গেট {flight.gate}। গেটের সাইন অনুসরণ করুন।",
            f"Your boarding gate is {flight.gate}. Follow the gate signs.",
        )
    elif kind == FlightEvent.KIND_GATE_CHANGE:
        flight.gate = gate or flight.gate
        update_fields.append("gate")
        messages = (
            f"গুরুত্বপূর্ণ: আপনার বোর্ডিং গেট পরিবর্তন হয়ে {flight.gate} হয়েছে। এখনই নতুন গেটের দিকে যান।",
            f"Important: your boarding gate has changed to {flight.gate}. Please go to the new gate now.",
        )
    elif kind == FlightEvent.KIND_BOARDING:
        flight.status = Flight.STATUS_BOARDING
        update_fields.append("status")
        gate_bn = f"গেট {flight.gate}-এ" if flight.gate else "বোর্ডিং গেটে"
        gate_en = f"Gate {flight.gate}" if flight.gate else "the boarding gate"
        messages = (
            f"আপনার ফ্লাইটের বোর্ডিং শুরু হয়েছে। এখনই {gate_bn} যান।",
