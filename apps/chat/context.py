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

    if status == flight.STATUS_CANCELLED or engine.flight_missed(flight):
        lines.append(
            f"Scheduled departure was at {format_clock(flight.effective_departure, lang)}."
        )
    else:
        countdowns = engine.countdowns(journey)
        for c in countdowns:
            label = translate(c["key"], lang)
            if c["minutes"] > 0:
                lines.append(f"{label}: at {format_clock(c['at'], lang)}, {c['minutes']} minutes from now")
            else:
                lines.append(f"{label}: at {format_clock(c['at'], lang)} (already due)")
    return "\n".join(lines)


def navigation_context(journey, request, lang=DEFAULT_LANG):
    refresh_location_index()
    current = get_current_location(request)
    lines = []
    if current:
        name = current.name_bn if lang == "bn" else current.name_en
        lines.append(f"Passenger's current position: {current.code} ({name})")
    else:
        lines.append("Passenger's current position: unknown (suggest scanning a nearby QR marker)")

    if journey:
        action = engine.next_action(journey)
        target_key = action.get("nav_target") or STAGE_NAV_TARGETS.get(journey.stage)
        target, _notice = resolve_target(target_key, journey)
        origin = current or Location.objects.filter(code="ENTRY").first()
        route = find_route(origin, target) if target else None
        if route and route.steps:
            lines.append(
                f"Route from current position to {target.name_en}: about {route.distance_m} m "
                f"(~{route.walk_minutes} min walk), {len(route.steps)} steps:"
            )
            for i, step in enumerate(route.steps, 1):
                text = step.instruction_bn if lang == "bn" else step.instruction_en
                lines.append(f"  {i}. {text} ({step.distance_m} m)")
    return "\n".join(lines)


def places_context(lang=DEFAULT_LANG):
    lines = []
    for loc in Location.objects.order_by("kind", "code"):
        name = loc.name_bn if lang == "bn" else loc.name_en
        lines.append(f"- {name} ({loc.kind})")
    return "\n".join(lines)


def build_system_prompt(journey, request, lang=DEFAULT_LANG):
    spoken_style = SPOKEN_BANGLA_STYLE if lang == "bn" else ""
    return (
        "You are Dishari AI, the airport travel partner for Hazrat Shahjalal International Airport (DAC), "
        "Terminal 2, Dhaka. You guide departing passengers.\n"
        f"Reply ONLY in {LANG_NAMES.get(lang, 'English')}. Keep replies short (1-3 sentences), "
        "simple, calm and polite; use everyday words a first-time traveler understands.\n"
        f"{spoken_style}"
        "RULES:\n"
        "- Messages starting with '[সিস্টেম:' are internal operational updates, not passenger "
        "speech: absorb them silently and never reply to them directly.\n"
        "- Use ONLY the OPERATIONAL DATA below for any fact about the flight, counters, gates, "
        "times, status or directions. NEVER invent or guess these. If a fact is missing, say it is "
        "not available yet and suggest the nearest information desk.\n"
        "- 'Next action' is authoritative: if the passenger asks what to do, explain that action.\n"
        "- If the passenger asks for a place (counter, immigration, gate, toilet, food), give the "
        "route steps when available, one step at a time, with distances.\n"
        "- If the passenger sounds lost or anxious, reassure them and give ONE simple next step.\n"
        "- Medical emergency, lost passport or lost child: immediately tell them to contact the "
        "nearest airport staff; medical centre for illness, airport police/immigration help desk "
        "for documents, staff announcement for a lost child.\n"
        "- Connecting flights (transit): follow 'Transfers' signs to the transit desk, show "
        "passport + onward ticket, clear transit security, go to the next flight's gate.\n"
        "- Arrivals at Dhaka: arrival immigration, baggage claim (belt on screens), customs "
        "(red channel if declaring, else green), then exit.\n"
        "- Never discuss other passengers' data or anything outside airport travel assistance.\n\n"
        "OPERATIONAL DATA:\n"
        f"[Journey]\n{journey_context(journey, lang)}\n\n"
        f"[Position and route]\n{navigation_context(journey, request, lang)}\n\n"
        f"[Airport places]\n{places_context(lang)}\n\n"
        f"[Emergency resources]\n{emergency_context(lang)}\n"
    )
