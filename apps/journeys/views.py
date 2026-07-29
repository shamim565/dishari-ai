from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.i18n import DEFAULT_LANG, translate
from apps.journeys import engine
from apps.journeys.services import get_active_journey
from apps.navigation.views import STAGE_NAV_TARGETS

TRANSIT_STEPS = ["trans_step1", "trans_step2", "trans_step3", "trans_step4", "trans_step5"]
ARRIVAL_STEPS = ["arr_step1", "arr_step2", "arr_step3", "arr_step4", "arr_step5"]


def arrival_context(request):
    lang = request.session.get("lang", DEFAULT_LANG)
    if lang not in ("bn", "en"):
        lang = DEFAULT_LANG

    def build_steps(keys):
        return [
            {"title": translate(f"{key}_title", lang), "text": translate(f"{key}_text", lang)}
            for key in keys
        ]

    return {
        "transit_steps": build_steps(TRANSIT_STEPS),
        "arrival_steps": build_steps(ARRIVAL_STEPS),
    }


def arrival_guide(request):
    return redirect(f"{reverse('home')}?view=arrival")
