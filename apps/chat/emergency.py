from apps.core.i18n import DEFAULT_LANG, translate
from apps.navigation.models import Location

MEDICAL_KEYWORDS = [
    "অসুস্থ", "অসুস্থতা", "শরীর খারাপ", "প্রেসার", "হার্ট", "শ্বাস",
    "sick", "unwell", "heart", "breathing", "medical", "fever", "ঢলে পড়ে",
]
DOCUMENT_KEYWORDS = [
    "পাসপোর্ট হারিয়ে", "পাসপোর্ট হারিয়ে", "টিকিট হারিয়ে", "টিকিট হারিয়ে",
    "passport lost", "lost my passport", "lost passport", "lost ticket", "ticket lost",
]
CHILD_KEYWORDS = [
    "বাচ্চা", "শিশু", "সন্তান", "মেয়ে হারিয়ে", "ছেলে হারিয়ে", "মেয়ে হারিয়ে", "ছেলে হারিয়ে",
    "child", "lost my child", "lost child", "my kid",
]

EMERGENCY_SPECS = {
    "medical": {
        "title_key": "emg_medical_title",
        "text_key": "emg_medical_text",
        "target": "MED",
        "keywords": MEDICAL_KEYWORDS,
    },
    "documents": {
        "title_key": "emg_doc_title",
        "text_key": "emg_doc_text",
        "target": "POLICE",
        "keywords": DOCUMENT_KEYWORDS,
    },
    "child": {
        "title_key": "emg_child_title",
        "text_key": "emg_child_text",
        "target": "INFO",
        "keywords": CHILD_KEYWORDS,
    },
}


def _matches(message, keywords):
    text = message.lower()
    return any(keyword.lower() in text for keyword in keywords)


def detect_emergency(message, lang=DEFAULT_LANG):
    for code, spec in EMERGENCY_SPECS.items():
        if not _matches(message, spec["keywords"]):
            continue
        title = translate(spec["title_key"], lang)
        text = translate(spec["text_key"], lang)
        location = Location.objects.filter(code=spec["target"]).first()
        target_name = ""
        if location:
            target_name = location.name_bn if lang == "bn" else location.name_en
        return {
            "code": code,
            "text": f"{title}. {text}",
            "event": {
                "emergency": {
                    "code": code,
                    "title": title,
                    "text": text,
                    "target": spec["target"],
                    "target_name": target_name,
                    "nav_label": translate("navigate_btn", lang),
                }
            },
        }
    return None
