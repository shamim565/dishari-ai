from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.flights.models import Flight
from apps.journeys.models import default_token


def default_handoff_expiry():
    return timezone.now() + timedelta(minutes=15)


class TicketScan(models.Model):
    SOURCE_UPLOAD = "upload"
    SOURCE_DEMO = "demo"
    SOURCE_CHOICES = [(SOURCE_UPLOAD, "Upload"), (SOURCE_DEMO, "Demo")]

    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD)
    success = models.BooleanField(default=False)
    error_code = models.CharField(max_length=40, blank=True)
    provider = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=60, blank=True)
    raw_extraction = models.JSONField(default=dict, blank=True)
    flight = models.ForeignKey(Flight, null=True, blank=True, on_delete=models.SET_NULL, related_name="ticket_scans")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.source} {'ok' if self.success else self.error_code}"


class TicketHandoff(models.Model):
    """Pairs a kiosk session with the passenger's phone.

    The kiosk shows a QR for ``/t/<token>/``; the phone uploads the ticket
    against this token; the kiosk polls and attaches the finished journey.
    """

    STATUS_PENDING = "pending"
    STATUS_READY = "ready"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Waiting for phone"),
        (STATUS_READY, "Ticket received"),
    ]

    token = models.CharField(max_length=64, unique=True, default=default_token)
    lang = models.CharField(max_length=2, choices=[("bn", "Bangla"), ("en", "English")], default="bn")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    journey = models.ForeignKey(
        "journeys.JourneySession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handoffs",
    )
    phone_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_handoff_expiry)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.token[:8]}… {self.status}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at
