from django.contrib import admin

from apps.flights.models import Airline, Airport, Flight


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "bangla_name")
    search_fields = ("code", "name")


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ("code", "city", "bangla_city")
    search_fields = ("code", "city")


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "airline",
        "origin",
        "destination",
        "date",
        "sched_departure",
        "est_departure",
        "status",
        "checkin_open",
        "checkin_block",
        "checkin_counters",
        "gate",
    )
    list_filter = ("status", "date", "airline", "checkin_open")
    search_fields = ("number",)
    date_hierarchy = "date"
