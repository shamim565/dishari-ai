from django.contrib import admin

from apps.journeys.models import JourneySession


@admin.register(JourneySession)
class JourneySessionAdmin(admin.ModelAdmin):
    list_display = ("passenger_name", "flight", "stage", "source", "lang", "created_at", "expires_at")
    list_filter = ("stage", "source", "lang")
    search_fields = ("passenger_name", "token", "pnr")
    readonly_fields = ("token", "created_at")
    date_hierarchy = "created_at"
