from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.chat.models import ChatMessage
from apps.journeys.models import JourneySession
from apps.tickets.models import TicketHandoff


class Command(BaseCommand):
    help = "Delete expired journey sessions and stale chat messages (kiosk housekeeping)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--grace-hours",
            type=int,
            default=24,
            help="Keep expired journeys for this many hours before deleting (default: 24).",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=options["grace_hours"])

        journeys = JourneySession.objects.filter(expires_at__lt=cutoff)
        journey_count = journeys.count()
        ChatMessage.objects.filter(journey__in=journeys).delete()
        journeys.delete()

        anonymous = ChatMessage.objects.filter(journey__isnull=True, created_at__lt=cutoff)
        anonymous_count = anonymous.count()
        anonymous.delete()

        handoffs = TicketHandoff.objects.filter(expires_at__lt=cutoff)
        handoff_count = handoffs.count()
        handoffs.delete()

        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        session_count = expired_sessions.count()
        expired_sessions.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Purged {journey_count} journey(s), {anonymous_count} stale chat message(s), "
                f"{handoff_count} expired ticket handoff(s), "
                f"{session_count} expired browser session(s)."
            )
        )
