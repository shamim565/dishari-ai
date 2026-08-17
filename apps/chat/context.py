from apps.core.i18n import DEFAULT_LANG, translate
from apps.core.times import format_clock
from apps.journeys import engine
from apps.navigation.engine import find_route, refresh_location_index
from apps.navigation.models import Location
from apps.navigation.views import STAGE_NAV_TARGETS, get_current_location, resolve_target

LANG_NAMES = {"bn": "Bangla (Bengali script, everyday Bangladeshi style)", "en": "English"}

SPOKEN_BANGLA_STYLE = (
    "\nSPOKEN BANGLA STYLE (the reply is read aloud by a Bengali voice):\n"
    "- Write the way Bangladeshis actually speak, not formal written Bangla.\n"
    "- Keep common English words that Bangladeshis say in English, written in Bangla "
    "script: ফ্লাইট, গেট, চেক-ইন, বোর্ডিং পাস, টার্মিনাল, ব্যাগেজ, কাস্টমস, "
    "ইমিগ্রেশন, ফাইনাল কল, কাউন্টার, ব্লক, সিট, পাসপোর্ট, ভিসা, ডিউটি ফ্রি।\n"
    "- Never translate those into pure Bangla (for example: never say উড়ান for flight).\n"
    "- Write the assistant name as দিশারী এআই.\n"
    "- Flight numbers: write letters and digits in Bangla, like বি এস ৩২২.\n"
    "- Times: write like রাত ৮:৩০ or সন্ধ্যা সাড়ে ৭টা.\n"
    "- No emojis, no markdown, no English letters inside Bangla sentences.\n"
    '- Good example: "আপনার ফ্লাইট বি এস ৩২২-এর গেট ১২ নম্বর। এখনই সেখানে যান।"\n'
)


def journey_context(journey, lang=DEFAULT_LANG):
    if not journey:
        return "No verified journey session. The passenger is in general assistant mode."

    flight = journey.flight
    action = engine.next_action(journey)
    status = flight.effective_status()
    prefix = "ফ্লাইট" if lang == "bn" else "Flight"
    lines = [
        f"{prefix}: {flight.number}, {flight.airline.name}",
        f"Route: {flight.origin.city} ({flight.origin.code}) to {flight.destination.city} ({flight.destination.code})",
        f"Date: {flight.date}, scheduled departure: {format_clock(flight.sched_departure, lang)}",
    ]
    if flight.est_departure and flight.est_departure != flight.sched_departure:
        lines.append(f"Estimated departure (delayed): {format_clock(flight.est_departure, lang)}")
    lines.append(f"Status: {translate('status_' + status.lower(), lang)}")
    lines.append(f"Terminal: {flight.terminal or 'Terminal 2'}")
    if flight.checkin_counters:
        lines.append(
            f"Check-in counters: {flight.checkin_counters}"
            + (f", block {flight.checkin_block}" if flight.checkin_block else "")
        )
    if flight.checkin_open:
        lines.append("Check-in is currently OPEN.")
    else:
        lines.append("Check-in has NOT opened yet.")
    lines.append(f"Gate: {flight.gate if flight.gate else 'not assigned yet'}")
    lines.append(
        f"Passenger: {journey.passenger_name}"
        + (f", seat {journey.seat}" if journey.seat else "")
    )
    lines.append(f"Journey stage: {journey.get_stage_display()} (stage code {journey.stage})")
    if status == flight.STATUS_CANCELLED:
        lines.append(
            "IMPORTANT: this flight is CANCELLED. Do not guide the passenger to check-in, "
            "immigration, security or the gate — direct them to the information desk / "
            "airline assistance counter."
        )
    elif engine.flight_missed(flight):
        lines.append(
            "IMPORTANT: this flight has ALREADY DEPARTED / its gate is closed — the "
            "passenger has missed it. Do not guide them to check-in, immigration, security "
            "or the gate — direct them to the information desk / airline assistance counter."
        )
    lines.append(f"Next action: {translate(action['title_key'], lang)}")
    lines.append(f"Next action detail: {translate(action['note_key'], lang)}")
    if action.get("warning_key"):
        lines.append(f"Warning: {translate(action['warning_key'], lang)}")
