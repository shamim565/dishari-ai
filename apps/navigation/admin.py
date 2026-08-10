from django.contrib import admin

from apps.navigation.models import Location, RouteSegment


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name_en", "kind", "block", "x", "y", "qr_code", "label_visible")
    list_filter = ("kind", "label_visible")
    search_fields = ("code", "name_en", "name_bn", "qr_code")


@admin.register(RouteSegment)
class RouteSegmentAdmin(admin.ModelAdmin):
    list_display = ("from_location", "to_location", "distance_m", "instruction_en")
    list_filter = ("from_location__kind", "to_location__kind")
