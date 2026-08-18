from apps.core.i18n import DEFAULT_LANG, translate
from apps.core.times import format_clock
from apps.journeys import engine
from apps.navigation.engine import find_route, refresh_location_index
from apps.navigation.models import Location
from apps.navigation.views import (
    STAGE_NAV_TARGETS,
    get_current_location,
    resolve_target,
)

GREETING = {
    "bn": "আসসালামু আলাইকুম! আমি দিশারী এআই — আপনার এয়ারপোর্ট সঙ্গী। যা জানতে চান জিজ্ঞেস করুন।",
    "en": "Hello! I am Dishari AI, your airport companion. Ask me anything about your journey.",
}

DEMO_NOTICE = {
    "bn": " (ডেমো মোডে আছি — সীমিত উত্তর দিতে পারি।)",
    "en": " (I am in demo mode — my answers are limited right now.)",
}

FALLBACK = {
    "bn": "এখন আমি নিশ্চিতভাবে বুঝতে পারিনি। কাছের ইনফরমেশন ডেস্কে জিজ্ঞেস করতে পারেন, অথবা জিজ্ঞেস করুন: \u201cএখন আমি কী করব?\u201d বা \u201cগেট কোথায়?\u201d",
    "en": "I could not understand that confidently. You can ask the nearest information desk, or try: \u201cWhat should I do now?\u201d or \u201cWhere is my gate?\u201d",
}

KEYWORDS = {
    "next": [
        "কী করব",
        "কি করব",
        "কী করতে",
        "কি করতে",
        "পরের কাজ",
        "what should i do",
        "what do i do",
        "next step",
    ],
    "gate": ["গেট", "gate"],
    "time": ["কত সময়", "কতক্ষণ", "কত ক্ষণ", "time left", "how long", "how much time"],
    "counter": [
        "চেক-ইন",
        "চেক ইন",
        "কাউন্টার",
        "counter",
        "check-in",
        "checkin",
        "চেকইন",
    ],
    "immigration": ["ইমিগ্রেশন", "immigration"],
    "security": ["সিকিউরিটি", "security"],
    "toilet": ["টয়লেট", "toilet", "washroom", "বাথরুম"],
    "food": ["খাবার", "খেতে", "food", "restaurant", "খাওয়া"],
    "toairside": ["এয়ারসাইড", "airside"],
    "lost": ["হারিয়ে", "হারিয়ে", "lost", "পথ হারিয়েছি"],
    "transit": [
        "ট্রানজিট",
        "কানেক্টিং",
        "কানেকশন",
        "connecting",
        "transit",
        "transfer",
        "পরবর্তী ফ্লাইট",
        "onward",
    ],
    "arrival": ["আগমন", "নেমে", "নামার পর", "arrival", "arrive", "landed", "landing"],
    "baggage": ["ব্যাগ", "লাগেজ", "baggage", "luggage", "ব্যাগেজ"],
    "customs": ["কাস্টমস", "customs", "ঘোষণা"],
}

TOPIC_LABELS = {
    "next": "Next action",
    "gate": "Gate",
    "time": "Time left",
    "counter": "Check-in counter",
    "immigration": "Immigration",
    "security": "Security",
    "toilet": "Toilets",
    "food": "Food",
    "toairside": "Airside",
    "lost": "Lost / navigation",
    "transit": "Transit",
    "arrival": "Arrival",
    "baggage": "Baggage",
    "customs": "Customs",
}


def _contains(message, key):
    text = message.lower()
    return any(token in text for token in KEYWORDS[key])


def detect_topic(message):
    for key in KEYWORDS:
        if _contains(message, key):
            return key
    return "other"


def _handoff_event(request, lang):
    refresh_location_index()
    current = get_current_location(request)
    info = Location.objects.filter(code="INFO").first()
    distance = None
    if current and info:
        route = find_route(current, info)
        if route:
            distance = route.distance_m
    text = translate("handoff_text", lang)
    if distance:
        if lang == "bn":
            text += f" আপনার বর্তমান অবস্থান থেকে প্রায় {distance} মিটার।"
        else:
            text += f" About {distance} m from your current position."
    return {
        "handoff": {
            "title": translate("handoff_title", lang),
            "text": text,
            "target": "INFO",
            "target_name": (
                info.name_bn
                if lang == "bn" and info
                else (info.name_en if info else "")
            ),
            "nav_label": translate("navigate_btn", lang),
        }
    }


def _reply(text, events=None):
    return {"text": text, "events": events or []}


def demo_reply(message, journey, request, lang=DEFAULT_LANG):
    if _contains(message, "next"):
        if not journey:
            base = {
                "bn": "প্রথমে টিকিট স্ক্যান করুন — তারপর আমি ধাপে ধাপে পথ দেখাব।",
                "en": "First scan your ticket — then I will guide you step by step.",
            }[lang]
            return _reply(base + DEMO_NOTICE[lang])
        action = engine.next_action(journey)
        title = translate(action["title_key"], lang)
        note = translate(action["note_key"], lang)
        reply = f"{title}। {note}"
        warning = action.get("warning_key")
        if warning:
            reply += " " + translate(warning, lang)
        if action["state"] == "done":
            reply += (
                " "
                + {
                    "bn": "এরপর ট্রানজিট ও আগমন গাইড দেখতে পারেন।",
                    "en": "You can check the Transit & Arrival guide next.",
                }[lang]
            )
        return _reply(reply + DEMO_NOTICE[lang])

    if _contains(message, "transit"):
        reply = {
            "bn": "কানেক্টিং ফ্লাইট থাকলে প্লেন থেকে নেমে 'Transfers' সাইন অনুসরণ করুন। ট্রান্সফার ডেস্কে পাসপোর্ট ও পরবর্তী টিকিট দেখান, তারপর ট্রানজিট সিকিউরিটি পার হয়ে পরবর্তী ফ্লাইটের গেটে যান।",
            "en": "If you have a connecting flight, follow the 'Transfers' sign after leaving the aircraft. Show your passport and onward ticket at the transfer desk, clear transit security, then go to your next flight's gate.",
        }[lang]
        return _reply(reply + DEMO_NOTICE[lang])
