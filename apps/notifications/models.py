from django.db import models

from apps.flights.models import Flight


class FlightEvent(models.Model):
    KIND_CHECK_IN_OPEN = "CHECK_IN_OPEN"
    KIND_COUNTER_CHANGE = "COUNTER_CHANGE"
    KIND_GATE_ASSIGNED = "GATE_ASSIGNED"
    KIND_GATE_CHANGE = "GATE_CHANGE"
    KIND_BOARDING = "BOARDING"
    KIND_FINAL_CALL = "FINAL_CALL"
    KIND_DELAY = "DELAY"
    KIND_CANCELLED = "CANCELLED"
    KIND_CHOICES = [
        (KIND_CHECK_IN_OPEN, "Check-in opened"),
        (KIND_COUNTER_CHANGE, "Counter changed"),
        (KIND_GATE_ASSIGNED, "Gate assigned"),
        (KIND_GATE_CHANGE, "Gate changed"),
        (KIND_BOARDING, "Boarding started"),
        (KIND_FINAL_CALL, "Final call"),
        (KIND_DELAY, "Delayed"),
        (KIND_CANCELLED, "Cancelled"),
    ]

    PRIORITY_NORMAL = "normal"
    PRIORITY_URGENT = "urgent"
    PRIORITY_CHOICES = [(PRIORITY_NORMAL, "Normal"), (PRIORITY_URGENT, "Urgent")]

    URGENT_KINDS = {KIND_GATE_CHANGE, KIND_FINAL_CALL, KIND_CANCELLED}

    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    message_bn = models.TextField()
    message_en = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_NORMAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.flight.number} {self.kind} @ {self.created_at:%H:%M}"

    def message(self, lang):
        return self.message_bn if lang == "bn" else self.message_en

    @property
    def is_urgent(self):
        return self.priority == self.PRIORITY_URGENT
