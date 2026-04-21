from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TrackerDevice(models.Model):
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="tracker_devices",
    )
    device_id = models.CharField(max_length=100, unique=True)
    api_key = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["device_id"]
        indexes = [
            models.Index(fields=["device_id"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.device_id} - {self.asset.asset_tag}"

    @property
    def latest_reading(self):
        return self.gps_readings.order_by("-recorded_at", "-pk").first()


class GPSReading(models.Model):
    device = models.ForeignKey(
        TrackerDevice,
        on_delete=models.CASCADE,
        related_name="gps_readings",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = models.FloatField(null=True, blank=True)
    speed_kmh = models.FloatField(null=True, blank=True)
    battery_level = models.PositiveSmallIntegerField(null=True, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    raw_payload = models.TextField(blank=True)

    class Meta:
        ordering = ["-recorded_at", "-pk"]
        indexes = [
            models.Index(fields=["device", "recorded_at"]),
        ]

    def __str__(self):
        return (
            f"{self.device.device_id} @ {self.recorded_at:%Y-%m-%d %H:%M:%S} "
            f"({self.latitude}, {self.longitude})"
        )

    def clean(self):
        super().clean()

        latitude = self._to_decimal(self.latitude, "latitude")
        longitude = self._to_decimal(self.longitude, "longitude")

        errors = {}
        if latitude is not None and not Decimal("-90") <= latitude <= Decimal("90"):
            errors["latitude"] = "Latitude must be between -90 and 90 degrees."
        if longitude is not None and not Decimal("-180") <= longitude <= Decimal("180"):
            errors["longitude"] = "Longitude must be between -180 and 180 degrees."
        if self.battery_level is not None and not 0 <= self.battery_level <= 100:
            errors["battery_level"] = "Battery level must be between 0 and 100."
        if errors:
            raise ValidationError(errors)

    @staticmethod
    def _to_decimal(value, field_name):
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError({field_name: "Enter a valid coordinate value."}) from exc
