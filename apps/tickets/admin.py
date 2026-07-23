from django.contrib import admin

from apps.tickets.models import TicketHandoff, TicketScan


@admin.register(TicketScan)
class TicketScanAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source", "success", "error_code", "flight", "provider", "model")
    list_filter = ("source", "success", "provider")
    search_fields = ("error_code", "flight__number")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(TicketHandoff)
class TicketHandoffAdmin(admin.ModelAdmin):
    list_display = ("created_at", "token", "status", "lang", "journey", "expires_at")
    list_filter = ("status", "lang")
    search_fields = ("token", "journey__passenger_name", "journey__flight__number")
    readonly_fields = ("token", "created_at")
