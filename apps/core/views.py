from django.contrib.staticfiles import finders
from django.db import connection
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect

from apps.core.i18n import DEFAULT_LANG, LANGS, strings_for
from apps.core.utils import safe_next


def health(request):
    """Liveness probe for the container stack (no session side effects)."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False
    return JsonResponse(
        {"status": "ok" if db_ok else "degraded", "db": db_ok},
        status=200 if db_ok else 503,
    )


def set_lang(request, code):
    if code in LANGS:
        request.session["lang"] = code
        request.session["lang_chosen"] = True
    return redirect(safe_next(request.GET.get("next")) or "home")
