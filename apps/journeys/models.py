import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone

from apps.flights.models import Flight


def default_token():
    return uuid.uuid4().hex


def default_expiry():
    return timezone.now() + timedelta(hours=12)


class JourneySession(models.Model):
    STAGE_ENTERED = "ENTERED"
    STAGE_CHECK_IN = "CHECK_IN"
    STAGE_IMMIGRATION = "IMMIGRATION"
    STAGE_SECURITY = "SECURITY"
    STAGE_AIRSIDE = "AIRSIDE"
    STAGE_GATE = "GATE"
    STAGE_BOARDED = "BOARDED"
    STAGE_CHOICES = [
        (STAGE_ENTERED, "Entered airport"),
        (STAGE_CHECK_IN, "Check-in"),
        (STAGE_IMMIGRATION, "Immigration"),
        (STAGE_SECURITY, "Security"),
        (STAGE_AIRSIDE, "Airside"),
        (STAGE_GATE, "Find boarding gate"),
        (STAGE_BOARDED, "Boarded"),
    ]

    SOURCE_UPLOAD = "upload"
    SOURCE_DEMO = "demo"
    SOURCE_CHOICES = [(SOURCE_UPLOAD, "Ticket upload"), (SOURCE_DEMO, "Demo ticket")]

    token = models.CharField(max_length=64, unique=True, default=default_token)
    passenger_name = models.CharField(max_length=100)
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name="journeys")
    seat = models.CharField(max_length=10, blank=True)
    pnr = models.CharField(max_length=12, blank=True)
    cabin = models.CharField(max_length=20, blank=True)
    lang = models.CharField(max_length=2, choices=[("bn", "Bangla"), ("en", "English")], default="en")
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default=STAGE_ENTERED)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_DEMO)
    extraction = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.passenger_name} · {self.flight.number} · {self.stage}"

    @property
    def is_active(self):
        return timezone.now() < self.expires_at
