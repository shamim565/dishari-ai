from django.db import models


class Location(models.Model):
    KIND_ENTRANCE = "entrance"
    KIND_CHECKIN = "checkin"
    KIND_IMMIGRATION = "immigration"
    KIND_SECURITY = "security"
    KIND_AIRSIDE = "airside"
    KIND_GATE = "gate"
    KIND_INFO = "info"
    KIND_TOILET = "toilet"
    KIND_PRAYER = "prayer"
    KIND_FOOD = "food"
    KIND_MEDICAL = "medical"
    KIND_CHOICES = [
        (KIND_ENTRANCE, "Entrance"),
        (KIND_CHECKIN, "Check-in"),
        (KIND_IMMIGRATION, "Immigration"),
        (KIND_SECURITY, "Security"),
        (KIND_AIRSIDE, "Airside"),
        (KIND_GATE, "Gate"),
        (KIND_INFO, "Information desk"),
        (KIND_TOILET, "Toilet"),
        (KIND_PRAYER, "Prayer room"),
        (KIND_FOOD, "Food"),
        (KIND_MEDICAL, "Medical"),
    ]

    code = models.CharField(max_length=20, unique=True)
    name_en = models.CharField(max_length=60)
    name_bn = models.CharField(max_length=80)
    map_label = models.CharField(max_length=12, blank=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    block = models.CharField(max_length=4, blank=True)
    x = models.PositiveIntegerField()
    y = models.PositiveIntegerField()
    qr_code = models.CharField(max_length=12, blank=True, unique=True, null=True)
    label_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "code"]

    def __str__(self):
        return f"{self.code} · {self.name_en}"


class RouteSegment(models.Model):
    from_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="segments_from")
    to_location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="segments_to")
    instruction_en = models.CharField(max_length=220)
    instruction_bn = models.CharField(max_length=260)
    distance_m = models.PositiveIntegerField(default=50)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["from_location", "to_location"], name="unique_segment_pair")]
        ordering = ["from_location", "to_location"]

    def __str__(self):
        return f"{self.from_location.code} -> {self.to_location.code} ({self.distance_m}m)"
