from django.conf import settings

from apps.core.i18n import DEFAULT_LANG, LANGS, Translator


def i18n(request):
    lang = request.session.get("lang", DEFAULT_LANG)
    if lang not in LANGS:
        lang = DEFAULT_LANG
    return {
        "t": Translator(lang),
        "lang": lang,
        "other_lang": "en" if lang == "bn" else "bn",
    }
