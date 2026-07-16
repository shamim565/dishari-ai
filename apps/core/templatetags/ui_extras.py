from django import template

from apps.core.i18n import translate
from apps.core.times import format_clock

register = template.Library()

STATUS_CLASSES = {
    "SCHEDULED": "chip-neutral",
    "CHECK_IN_OPEN": "chip-success",
    "CHECK_IN_CLOSED": "chip-muted",
    "DELAYED": "chip-warn",
    "BOARDING": "chip-success",
    "FINAL_CALL": "chip-danger",
    "GATE_CLOSED": "chip-muted",
    "DEPARTED": "chip-muted",
    "CANCELLED": "chip-danger",
}


@register.filter
def status_label(status_code, lang="en"):
    return translate(f"status_{str(status_code).lower()}", lang)


@register.filter
def status_class(status_code):
    return STATUS_CLASSES.get(str(status_code).upper(), "chip-neutral")


@register.filter
def bn_name(obj, lang="en"):
    if lang == "bn":
        value = getattr(obj, "bangla_name", "") or getattr(obj, "bangla_city", "")
        if value:
            return value
    return getattr(obj, "name", "") or getattr(obj, "city", "") or str(obj)


@register.filter
def city_name(airport, lang="en"):
    if lang == "bn" and airport.bangla_city:
        return airport.bangla_city
    return airport.city


@register.filter
def airport_time(value, lang="en"):
    return format_clock(value, lang)


@register.filter
def tkey(key, lang="en"):
    return translate(key, lang)


@register.filter
def duration_label(minutes, lang="en"):
