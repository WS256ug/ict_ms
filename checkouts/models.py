import math

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class CheckoutRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Approval"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("CHECKED_OUT", "Checked Out"),
        ("RETURNED", "Returned"),
        ("OVERDUE", "Overdue"),
        ("CANCELLED", "Cancelled"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    ACTIVE_STATUSES = ("APPROVED", "CHECKED_OUT", "OVERDUE")

    request_number = models.CharField(max_length=50, unique=True, editable=False)
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="checkouts",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="checkout_requests",
    )
    requester_department = models.ForeignKey(
        "accounts.Department",
        on_delete=models.CASCADE,
        related_name="checkout_requests",
    )
    requester_phone = models.CharField(max_length=20)
    purpose = models.TextField(help_text="Purpose or reason for the checkout.")
    intended_location = models.CharField(
        max_length=300,
        help_text="Where the asset will be used.",
    )
    requested_date = models.DateTimeField(default=timezone.now)
    requested_checkout_date = models.DateField(help_text="Requested checkout date.")
    requested_return_date = models.DateField(help_text="Requested return date.")
    actual_checkout_date = models.DateTimeField(null=True, blank=True)
    actual_return_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="NORMAL")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_checkouts",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    checked_out_by_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_checkouts",
    )
    returned_to_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_returns",
    )
    condition_at_checkout = models.TextField(
        blank=True,
        help_text="Asset condition when checked out.",
    )
    condition_at_return = models.TextField(
        blank=True,
        null=True,
        help_text="Asset condition when returned.",
    )
    damage_reported = models.BooleanField(default=False)
    damage_description = models.TextField(blank=True, null=True)
    damage_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated repair or replacement cost.",
    )
    notes = models.TextField(blank=True, null=True)
    internal_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Admin-only notes.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_date"]
        verbose_name = "Checkout Request"
        verbose_name_plural = "Checkout Requests"
        indexes = [
            models.Index(fields=["request_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["requested_by"]),
            models.Index(fields=["requested_checkout_date", "requested_return_date"]),
        ]

    def __str__(self):
        return f"{self.request_number} - {self.asset.asset_tag} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        errors = {}

        if self.requested_checkout_date and self.requested_return_date:
            if self.requested_return_date < self.requested_checkout_date:
                errors["requested_return_date"] = "Return date must be on or after checkout date."
            elif self.asset_id:
                requested_days = self.requested_duration_days
                if requested_days > self.asset.max_checkout_days:
                    errors["requested_return_date"] = (
                        f"Maximum checkout duration for this asset is {self.asset.max_checkout_days} days."
                    )

        if self.asset_id:
            if not self.asset.is_portable:
                errors["asset"] = "This asset cannot be checked out."
            elif self.asset.status != "ACTIVE":
                errors["asset"] = "Only active assets can be checked out."
            else:
                active_checkout_exists = self.asset.checkouts.exclude(pk=self.pk).filter(
                    status__in=self.ACTIVE_STATUSES
                ).exists()
                if active_checkout_exists and self.status in self.ACTIVE_STATUSES:
                    errors["asset"] = "This asset already has an active checkout."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self._generate_request_number()
        super().save(*args, **kwargs)

    def _generate_request_number(self):
        year = timezone.now().year
        prefix = f"CHK-{year}-"
        last_request = (
            CheckoutRequest.objects.filter(request_number__startswith=prefix)
            .order_by("-request_number")
            .values_list("request_number", flat=True)
            .first()
        )
        next_number = 1
        if last_request:
            try:
                next_number = int(last_request.rsplit("-", 1)[-1]) + 1
            except (TypeError, ValueError):
                next_number = CheckoutRequest.objects.filter(
                    request_number__startswith=prefix
                ).count() + 1
        return f"{prefix}{next_number:04d}"

    @property
    def is_overdue(self):
        if self.status in ("CHECKED_OUT", "OVERDUE"):
            return timezone.localdate() > self.requested_return_date
        return False

    @property
    def days_overdue(self):
        if self.is_overdue:
            return (timezone.localdate() - self.requested_return_date).days
        return 0

    @property
    def checkout_duration_days(self):
        if self.actual_checkout_date:
            end_date = self.actual_return_date or timezone.now()
            return max((end_date - self.actual_checkout_date).days, 0)
        return 0

    @property
    def requested_duration_days(self):
        if self.requested_checkout_date and self.requested_return_date:
            return max((self.requested_return_date - self.requested_checkout_date).days, 0)
        return 0


class GPSLocation(models.Model):
    checkout = models.ForeignKey(
        CheckoutRequest,
        on_delete=models.CASCADE,
        related_name="gps_locations",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    accuracy_meters = models.FloatField(help_text="GPS accuracy in meters.")
    altitude = models.FloatField(null=True, blank=True, help_text="Altitude in meters.")
    speed_kmh = models.FloatField(null=True, blank=True, help_text="Speed in km/h.")
    heading_degrees = models.FloatField(
        null=True,
        blank=True,
        help_text="Direction in degrees.",
    )
    battery_level = models.IntegerField(
        null=True,
        blank=True,
        help_text="Battery percentage (0-100).",
    )
    is_inside_geofence = models.BooleanField(default=True)
    distance_from_center_meters = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance from the configured geofence center.",
    )
    recorded_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name = "GPS Location"
        verbose_name_plural = "GPS Locations"
        indexes = [
            models.Index(fields=["checkout", "recorded_at"]),
        ]

    def __str__(self):
        return (
            f"{self.checkout.asset.asset_tag} @ {self.recorded_at:%Y-%m-%d %H:%M:%S} "
            f"({self.latitude}, {self.longitude})"
        )

    def calculate_distance_from_point(self, latitude, longitude):
        lat1 = math.radians(float(self.latitude))
        lon1 = math.radians(float(self.longitude))
        lat2 = math.radians(float(latitude))
        lon2 = math.radians(float(longitude))

        delta_lat = lat2 - lat1
        delta_lon = lon2 - lon1
        earth_radius_meters = 6371000

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return earth_radius_meters * c

    def save(self, *args, **kwargs):
        asset = self.checkout.asset
        if (
            asset.geofence_enabled
            and asset.geofence_latitude is not None
            and asset.geofence_longitude is not None
        ):
            self.distance_from_center_meters = self.calculate_distance_from_point(
                asset.geofence_latitude,
                asset.geofence_longitude,
            )
            self.is_inside_geofence = (
                self.distance_from_center_meters <= asset.geofence_radius_meters
            )
        else:
            self.distance_from_center_meters = None
            self.is_inside_geofence = True
        super().save(*args, **kwargs)


class GeofenceAlert(models.Model):
    ALERT_TYPE_CHOICES = [
        ("GEOFENCE_EXIT", "Asset Left Campus"),
        ("GEOFENCE_ENTRY", "Asset Returned to Campus"),
        ("LOW_BATTERY", "GPS Device Low Battery"),
        ("SIGNAL_LOST", "GPS Signal Lost"),
    ]

    checkout = models.ForeignKey(
        CheckoutRequest,
        on_delete=models.CASCADE,
        related_name="geofence_alerts",
    )
    gps_location = models.ForeignKey(
        GPSLocation,
        on_delete=models.CASCADE,
        related_name="alerts",
        null=True,
        blank=True,
    )
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    message = models.TextField()
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="geofence_alert_acknowledgements",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Geofence Alert"
        verbose_name_plural = "Geofence Alerts"
        indexes = [
            models.Index(fields=["alert_type", "is_resolved"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.checkout.asset.asset_tag}"


class CheckoutHistory(models.Model):
    checkout = models.ForeignKey(
        CheckoutRequest,
        on_delete=models.CASCADE,
        related_name="history",
    )
    previous_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Checkout History"
        verbose_name_plural = "Checkout Histories"
        indexes = [
            models.Index(fields=["checkout", "changed_at"]),
        ]

    def __str__(self):
        return f"{self.checkout.request_number}: {self.previous_status} -> {self.new_status}"
