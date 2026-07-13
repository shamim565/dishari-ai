from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone

# Time windows (minutes before/after departure) that define the effective phase.
CHECKIN_OPEN_LEAD_MINUTES = 180
CHECKIN_CLOSE_BEFORE_MINUTES = 60
BOARDING_BEFORE_MINUTES = 45
FINAL_CALL_BEFORE_MINUTES = 20
DEPARTED_GRACE_MINUTES = 15


class Airline(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=80)
    bangla_name = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Airport(models.Model):
    code = models.CharField(max_length=3, unique=True)
    city = models.CharField(max_length=60)
    name = models.CharField(max_length=120, blank=True)
    bangla_city = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["city"]

    def __str__(self):
        return f"{self.city} ({self.code})"


class Flight(models.Model):
    STATUS_SCHEDULED = "SCHEDULED"
    STATUS_CHECK_IN_OPEN = "CHECK_IN_OPEN"
    STATUS_CHECK_IN_CLOSED = "CHECK_IN_CLOSED"
    STATUS_DELAYED = "DELAYED"
    STATUS_BOARDING = "BOARDING"
    STATUS_FINAL_CALL = "FINAL_CALL"
    STATUS_GATE_CLOSED = "GATE_CLOSED"
    STATUS_DEPARTED = "DEPARTED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_CHECK_IN_OPEN, "Check-in open"),
        (STATUS_CHECK_IN_CLOSED, "Check-in closed"),
        (STATUS_DELAYED, "Delayed"),
        (STATUS_BOARDING, "Boarding"),
        (STATUS_FINAL_CALL, "Final call"),
        (STATUS_GATE_CLOSED, "Gate closed"),
        (STATUS_DEPARTED, "Departed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    STATUS_PHASE_ORDER = [
        STATUS_SCHEDULED,
        STATUS_CHECK_IN_OPEN,
        STATUS_CHECK_IN_CLOSED,
        STATUS_BOARDING,
        STATUS_FINAL_CALL,
        STATUS_GATE_CLOSED,
        STATUS_DEPARTED,
    ]

    number = models.CharField(max_length=10)
    airline = models.ForeignKey(Airline, on_delete=models.CASCADE, related_name="flights")
    origin = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name="departures")
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name="arrivals")
    date = models.DateField()
    sched_departure = models.TimeField()
    est_departure = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
    checkin_open = models.BooleanField(default=False)
    checkin_block = models.CharField(max_length=4, blank=True)
    checkin_counters = models.CharField(max_length=20, blank=True)
    gate = models.CharField(max_length=6, blank=True)
    terminal = models.CharField(max_length=20, blank=True)
    boarding_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
