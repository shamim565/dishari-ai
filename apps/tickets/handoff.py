"""Kiosk ⇄ phone ticket pairing helpers.

The kiosk session owns a :class:`~apps.tickets.models.TicketHandoff`; the QR
shown on the kiosk points at ``/t/<token>/``.  When the phone finishes the
upload, the kiosk polls and attaches the journey to its own session.
"""

from datetime import timedelta

from django.utils import timezone

from apps.core.i18n import DEFAULT_LANG, LANGS
from apps.tickets.models import TicketHandoff

HANDOFF_KEY = "ticket_handoff"

# While the passenger's phone has the upload page open it pings every 30 s;
# the kiosk keeps its idle-reset timer alive as long as a ping is this fresh.
HOLD_WINDOW = timedelta(seconds=75)


def current_lang(request):
    lang = request.session.get("lang", DEFAULT_LANG)
    return lang if lang in LANGS else DEFAULT_LANG


def ensure_handoff(request):
    """Return the kiosk's pending handoff, creating a fresh one when needed."""
    token = request.session.get(HANDOFF_KEY)
    handoff = TicketHandoff.objects.filter(token=token).first() if token else None
    if handoff and (handoff.is_expired or handoff.status != TicketHandoff.STATUS_PENDING):
        handoff = None
    if handoff is None:
        handoff = TicketHandoff.objects.create(lang=current_lang(request))
        request.session[HANDOFF_KEY] = handoff.token
    return handoff


def get_ready_handoff(request):
    """A finished handoff waiting to be picked up by the kiosk session."""
    token = request.session.get(HANDOFF_KEY)
    if not token:
        return None
    handoff = (
        TicketHandoff.objects.select_related("journey")
        .filter(token=token, status=TicketHandoff.STATUS_READY, journey__isnull=False)
        .first()
    )
    if not handoff or handoff.is_expired or not handoff.journey.is_active:
        return None
    return handoff


def mark_phone_seen(handoff):
    TicketHandoff.objects.filter(pk=handoff.pk).update(phone_seen_at=timezone.now())


def hold_active(handoff):
    """True while the passenger's phone is actively on the upload page."""
    if handoff.status != TicketHandoff.STATUS_PENDING or handoff.is_expired or not handoff.phone_seen_at:
        return False
    return timezone.now() - handoff.phone_seen_at <= HOLD_WINDOW
