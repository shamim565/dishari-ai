from django.utils import timezone

BANGLA_PERIODS = [
    (range(5, 12), "সকাল"),
    (range(12, 16), "দুপুর"),
    (range(16, 18), "বিকাল"),
    (range(18, 20), "সন্ধ্যা"),
]


def format_clock(value, lang="en"):
    if value is None:
        return ""
    if hasattr(value, "tzinfo") and value.tzinfo is not None:
        value = timezone.localtime(value)
    hour = value.hour
    minute = value.minute
    hour12 = hour % 12 or 12
    if lang == "bn":
        period = "রাত"
        for hours, label in BANGLA_PERIODS:
            if hour in hours:
                period = label
                break
        return f"{period} {hour12}:{minute:02d}"
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour12}:{minute:02d} {suffix}"
