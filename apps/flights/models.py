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

    class Meta:
        ordering = ["sched_departure"]
        constraints = [models.UniqueConstraint(fields=["number", "date"], name="unique_flight_per_day")]

    def __str__(self):
        return f"{self.number} {self.origin.code}->{self.destination.code} {self.date} {self.sched_departure}"

    @property
    def effective_departure(self):
        return self.est_departure or self.sched_departure

    @property
    def is_delayed(self):
        return bool(self.est_departure and self.est_departure != self.sched_departure) or self.status == self.STATUS_DELAYED

    def time_status(self, now=None):
        """The status implied by the clock alone (uses effective departure)."""
        now = now or timezone.now()
        departure = timezone.make_aware(
            datetime.combine(self.date, self.effective_departure),
            timezone.get_current_timezone(),
        )
        minutes = (departure - now).total_seconds() / 60
        if minutes <= -DEPARTED_GRACE_MINUTES:
            return self.STATUS_DEPARTED
        if minutes <= 0:
            return self.STATUS_GATE_CLOSED
        if minutes <= FINAL_CALL_BEFORE_MINUTES:
            return self.STATUS_FINAL_CALL
        if minutes <= BOARDING_BEFORE_MINUTES:
            return self.STATUS_BOARDING
        if minutes <= CHECKIN_CLOSE_BEFORE_MINUTES:
            return self.STATUS_CHECK_IN_CLOSED
        if minutes <= CHECKIN_OPEN_LEAD_MINUTES:
            return self.STATUS_CHECK_IN_OPEN
        return self.STATUS_SCHEDULED

    def effective_status(self, now=None):
        """Real-time-aware status.

        Manual statuses may advance the narrative early (ops control), but the
        clock always supersedes stale ones. CANCELLED always wins; DELAYED is
        respected through ``effective_departure`` (est_departure).
        """
        if self.status == self.STATUS_CANCELLED:
            return self.STATUS_CANCELLED
        time_phase = self.time_status(now)
        manual = self.status if self.status in self.STATUS_PHASE_ORDER else self.STATUS_SCHEDULED
        return max(time_phase, manual, key=self.STATUS_PHASE_ORDER.index)

    def display_status(self, now=None):
        """Chip-friendly status: the delayed badge wins over in-progress phases,
        but terminal states (departed / gate closed / cancelled) win over delayed."""
        status = self.effective_status(now)
        if status in (self.STATUS_DEPARTED, self.STATUS_GATE_CLOSED, self.STATUS_CANCELLED):
            return status
        if self.is_delayed:
            return self.STATUS_DELAYED
        return status

    @property
    def arrival_datetime(self):
        if not self.duration_minutes:
            return None
        departure = datetime.combine(self.date, self.effective_departure)
        return departure + timedelta(minutes=self.duration_minutes)

    @property
    def arrival_time(self):
        arrival = self.arrival_datetime
        return arrival.time().replace(second=0, microsecond=0) if arrival else None

    @property
    def arrives_next_day(self):
        arrival = self.arrival_datetime
        return bool(arrival and arrival.date() != self.date)
