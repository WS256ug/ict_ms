from django.contrib import admin

from .models import GPSReading, TrackerDevice


@admin.register(TrackerDevice)
class TrackerDeviceAdmin(admin.ModelAdmin):
    list_display = ("device_id", "asset", "is_active", "last_seen_at", "updated_at")
    list_filter = ("is_active", "created_at", "updated_at")
    search_fields = ("device_id", "asset__asset_tag", "asset__name")
    readonly_fields = ("last_seen_at", "created_at", "updated_at")
    autocomplete_fields = ("asset",)


@admin.register(GPSReading)
class GPSReadingAdmin(admin.ModelAdmin):
    list_display = (
        "device",
        "latitude",
        "longitude",
        "accuracy_meters",
        "speed_kmh",
        "battery_level",
        "recorded_at",
    )
    list_filter = ("recorded_at", "created_at")
    search_fields = ("device__device_id", "device__asset__asset_tag", "device__asset__name")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("device",)
