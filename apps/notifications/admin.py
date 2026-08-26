from django.contrib import admin

from apps.notifications.models import FlightEvent


@admin.register(FlightEvent)
class FlightEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "flight", "kind", "priority", "message_en")
    list_filter = ("kind", "priority")
    search_fields = ("flight__number", "message_bn", "message_en")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
