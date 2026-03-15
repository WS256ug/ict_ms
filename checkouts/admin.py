from django.contrib import admin
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import CheckoutHistory, CheckoutRequest, GPSLocation, GeofenceAlert


class GPSLocationInline(admin.TabularInline):
    model = GPSLocation
    extra = 0
    readonly_fields = (
        "latitude",
        "longitude",
        "accuracy_meters",
        "is_inside_geofence",
        "distance_from_center_meters",
        "battery_level",
        "recorded_at",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("-recorded_at")[:10]


class GeofenceAlertInline(admin.TabularInline):
    model = GeofenceAlert
    extra = 0
    readonly_fields = (
        "alert_type",
        "message",
        "is_acknowledged",
        "is_resolved",
        "created_at",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CheckoutHistoryInline(admin.TabularInline):
    model = CheckoutHistory
    extra = 0
    readonly_fields = (
        "previous_status",
        "new_status",
        "changed_by",
        "notes",
        "changed_at",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CheckoutRequest)
class CheckoutRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number",
        "asset",
        "requested_by",
        "status_badge",
        "priority_badge",
        "requested_checkout_date",
        "requested_return_date",
        "overdue_indicator",
        "gps_status",
        "created_at",
    )
    list_filter = (
        "status",
        "priority",
        "requested_checkout_date",
        "damage_reported",
        "created_at",
    )
    search_fields = (
        "request_number",
        "asset__asset_tag",
        "asset__name",
        "requested_by__email",
        "requested_by__first_name",
        "requested_by__last_name",
        "purpose",
    )
    readonly_fields = (
        "request_number",
        "created_at",
        "updated_at",
        "overdue_indicator",
        "checkout_duration_display",
        "gps_tracking_status",
        "view_gps_map",
    )
    fieldsets = (
        ("Request Information", {"fields": ("request_number", "asset", "status", "priority")}),
        (
            "Requester Details",
            {
                "fields": (
                    "requested_by",
                    "requester_department",
                    "requester_phone",
                    "purpose",
                    "intended_location",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "requested_checkout_date",
                    "requested_return_date",
                    "actual_checkout_date",
                    "actual_return_date",
                    "overdue_indicator",
                    "checkout_duration_display",
                )
            },
        ),
        ("Approval", {"fields": ("approved_by", "approved_at", "rejection_reason")}),
        (
            "Checkout/Return Processing",
            {"fields": ("checked_out_by_admin", "returned_to_admin")},
        ),
        (
            "Condition Tracking",
            {
                "fields": (
                    "condition_at_checkout",
                    "condition_at_return",
                    "damage_reported",
                    "damage_description",
                    "damage_cost",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "GPS Tracking",
            {"fields": ("gps_tracking_status", "view_gps_map"), "classes": ("collapse",)},
        ),
        ("Notes", {"fields": ("notes", "internal_notes"), "classes": ("collapse",)}),
        (
            "System Information",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    inlines = [CheckoutHistoryInline, GPSLocationInline, GeofenceAlertInline]
    list_per_page = 25
    date_hierarchy = "requested_checkout_date"
    actions = [
        "approve_requests",
        "reject_requests",
        "mark_checked_out",
        "mark_returned",
        "mark_overdue",
    ]

    def status_badge(self, obj):
        colors = {
            "PENDING": "#ffc107",
            "APPROVED": "#17a2b8",
            "REJECTED": "#dc3545",
            "CHECKED_OUT": "#007bff",
            "RETURNED": "#28a745",
            "OVERDUE": "#dc3545",
            "CANCELLED": "#6c757d",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def priority_badge(self, obj):
        colors = {
            "LOW": "#6c757d",
            "NORMAL": "#17a2b8",
            "HIGH": "#fd7e14",
            "URGENT": "#dc3545",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.priority, "#17a2b8"),
            obj.get_priority_display(),
        )

    priority_badge.short_description = "Priority"

    def overdue_indicator(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">&#9888; OVERDUE ({} days)</span>',
                obj.days_overdue,
            )
        if obj.status in ("CHECKED_OUT", "OVERDUE"):
            return format_html('<span style="color: green;">&#10003; On Time</span>')
        return "-"

    overdue_indicator.short_description = "Return Status"

    def gps_status(self, obj):
        if not obj.asset.has_gps_tracker:
            return format_html('<span style="color: gray;">No GPS</span>')
        if obj.status not in ("CHECKED_OUT", "OVERDUE"):
            return "-"

        latest_location = obj.gps_locations.first()
        if latest_location is None:
            return format_html('<span style="color: red;">No Signal</span>')

        time_diff = timezone.now() - latest_location.recorded_at
        if time_diff.total_seconds() < 300:
            return format_html('<span style="color: green;">LIVE</span>')
        return format_html(
            '<span style="color: orange;">Last: {} ago</span>',
            self._format_timedelta(time_diff),
        )

    gps_status.short_description = "GPS"

    def checkout_duration_display(self, obj):
        if not obj.actual_checkout_date:
            return f"Requested: {obj.requested_duration_days} days"

        duration = obj.checkout_duration_days
        requested = obj.requested_duration_days
        if obj.status == "RETURNED":
            if duration <= requested:
                return format_html(
                    '<span style="color: green;">{} days (within request)</span>',
                    duration,
                )
            return format_html(
                '<span style="color: orange;">{} days ({} days over)</span>',
                duration,
                duration - requested,
            )
        return f"{duration} days (ongoing)"

    checkout_duration_display.short_description = "Duration"

    def gps_tracking_status(self, obj):
        if not obj.asset.has_gps_tracker:
            return "GPS tracker not installed on this asset."

        location_count = obj.gps_locations.count()
        latest = obj.gps_locations.first()
        if latest is None:
            return "No GPS data received yet."

        status_html = [
            f"<div><strong>Total GPS Reports:</strong> {location_count}</div>",
            f"<div><strong>Latest Location:</strong> {latest.recorded_at:%Y-%m-%d %H:%M:%S}</div>",
            f"<div><strong>Coordinates:</strong> ({latest.latitude}, {latest.longitude})</div>",
            f"<div><strong>Accuracy:</strong> {latest.accuracy_meters:.1f}m</div>",
        ]

        if obj.asset.geofence_enabled and latest.distance_from_center_meters is not None:
            geofence_color = "green" if latest.is_inside_geofence else "red"
            geofence_label = "INSIDE CAMPUS" if latest.is_inside_geofence else "OUTSIDE CAMPUS"
            status_html.append(
                "<div><strong>Geofence Status:</strong> "
                f'<span style="color: {geofence_color};">{geofence_label}</span></div>'
            )
            status_html.append(
                f"<div><strong>Distance from Center:</strong> {latest.distance_from_center_meters:.0f}m</div>"
            )

        if latest.battery_level is not None:
            if latest.battery_level < 20:
                battery_color = "red"
            elif latest.battery_level < 50:
                battery_color = "orange"
            else:
                battery_color = "green"
            status_html.append(
                "<div><strong>Battery:</strong> "
                f'<span style="color: {battery_color};">{latest.battery_level}%</span></div>'
            )

        return format_html("".join(status_html))

    gps_tracking_status.short_description = "GPS Tracking Status"

    def view_gps_map(self, obj):
        if not obj.asset.has_gps_tracker or not obj.gps_locations.exists():
            return "No GPS data available"

        url = reverse("admin:checkouts_gpslocation_changelist")
        return format_html(
            '<a href="{}?checkout__id__exact={}" class="button">View GPS Reports</a>',
            url,
            obj.pk,
        )

    view_gps_map.short_description = "GPS Reports"

    def _format_timedelta(self, td):
        total_seconds = int(td.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours >= 24:
            days = hours // 24
            return f"{days}d {hours % 24}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def approve_requests(self, request, queryset):
        updated = 0
        for checkout in queryset.filter(status="PENDING"):
            checkout.status = "APPROVED"
            checkout.approved_by = request.user
            checkout.approved_at = timezone.now()
            checkout._changed_by = request.user
            try:
                checkout.full_clean()
            except ValidationError:
                continue
            checkout.save()
            updated += 1
        self.message_user(request, f"{updated} requests approved.")

    approve_requests.short_description = "Approve selected requests"

    def reject_requests(self, request, queryset):
        updated = 0
        for checkout in queryset.filter(status="PENDING"):
            checkout.status = "REJECTED"
            checkout.approved_by = request.user
            checkout.approved_at = timezone.now()
            checkout._changed_by = request.user
            checkout.save()
            updated += 1
        self.message_user(request, f"{updated} requests rejected.")

    reject_requests.short_description = "Reject selected requests"

    def mark_checked_out(self, request, queryset):
        updated = 0
        for checkout in queryset.filter(status="APPROVED"):
            checkout.status = "CHECKED_OUT"
            checkout.checked_out_by_admin = request.user
            checkout.actual_checkout_date = timezone.now()
            checkout._changed_by = request.user
            try:
                checkout.full_clean()
            except ValidationError:
                continue
            checkout.save()
            updated += 1
        self.message_user(request, f"{updated} assets marked as checked out.")

    mark_checked_out.short_description = "Mark as Checked Out"

    def mark_returned(self, request, queryset):
        updated = 0
        for checkout in queryset.filter(status__in=("CHECKED_OUT", "OVERDUE")):
            checkout.status = "RETURNED"
            checkout.returned_to_admin = request.user
            checkout.actual_return_date = timezone.now()
            checkout._changed_by = request.user
            checkout.save()
            updated += 1
        self.message_user(request, f"{updated} assets marked as returned.")

    mark_returned.short_description = "Mark as Returned"

    def mark_overdue(self, request, queryset):
        updated = 0
        for checkout in queryset.filter(
            status="CHECKED_OUT",
            requested_return_date__lt=timezone.localdate(),
        ):
            checkout.status = "OVERDUE"
            checkout._changed_by = request.user
            checkout.save()
            updated += 1
        self.message_user(request, f"{updated} checkouts marked as overdue.")

    mark_overdue.short_description = "Mark as Overdue"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "asset",
                "requested_by",
                "requester_department",
                "approved_by",
                "checked_out_by_admin",
                "returned_to_admin",
            )
            .prefetch_related("gps_locations", "geofence_alerts")
        )

    def save_model(self, request, obj, form, change):
        obj._changed_by = request.user
        if not obj.requester_department_id and obj.requested_by_id and obj.requested_by.department_id:
            obj.requester_department = obj.requested_by.department
        super().save_model(request, obj, form, change)


@admin.register(GPSLocation)
class GPSLocationAdmin(admin.ModelAdmin):
    list_display = (
        "checkout",
        "latitude",
        "longitude",
        "accuracy_meters",
        "geofence_status",
        "battery_level",
        "recorded_at",
    )
    list_filter = ("is_inside_geofence", "recorded_at")
    search_fields = ("checkout__request_number", "checkout__asset__asset_tag")
    readonly_fields = (
        "checkout",
        "latitude",
        "longitude",
        "accuracy_meters",
        "altitude",
        "speed_kmh",
        "heading_degrees",
        "is_inside_geofence",
        "distance_from_center_meters",
        "battery_level",
        "recorded_at",
        "created_at",
    )
    date_hierarchy = "recorded_at"

    def geofence_status(self, obj):
        if obj.is_inside_geofence:
            return format_html('<span style="color: green;">INSIDE</span>')
        return format_html('<span style="color: red;">OUTSIDE</span>')

    geofence_status.short_description = "Geofence"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GeofenceAlert)
class GeofenceAlertAdmin(admin.ModelAdmin):
    list_display = (
        "checkout",
        "alert_type_badge",
        "message_preview",
        "status_indicator",
        "created_at",
    )
    list_filter = ("alert_type", "is_acknowledged", "is_resolved", "created_at")
    search_fields = (
        "checkout__request_number",
        "checkout__asset__asset_tag",
        "message",
    )
    readonly_fields = ("checkout", "gps_location", "alert_type", "message", "created_at")
    fieldsets = (
        ("Alert Information", {"fields": ("checkout", "gps_location", "alert_type", "message")}),
        (
            "Management",
            {
                "fields": (
                    "is_acknowledged",
                    "acknowledged_by",
                    "acknowledged_at",
                    "is_resolved",
                    "resolution_notes",
                )
            },
        ),
        ("System Info", {"fields": ("created_at",), "classes": ("collapse",)}),
    )
    actions = ["acknowledge_alerts", "resolve_alerts"]

    def alert_type_badge(self, obj):
        colors = {
            "GEOFENCE_EXIT": "#dc3545",
            "GEOFENCE_ENTRY": "#28a745",
            "LOW_BATTERY": "#ffc107",
            "SIGNAL_LOST": "#6c757d",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.alert_type, "#6c757d"),
            obj.get_alert_type_display(),
        )

    alert_type_badge.short_description = "Alert Type"

    def message_preview(self, obj):
        return obj.message[:100] + "..." if len(obj.message) > 100 else obj.message

    message_preview.short_description = "Message"

    def status_indicator(self, obj):
        if obj.is_resolved:
            return format_html('<span style="color: green;">&#10003; Resolved</span>')
        if obj.is_acknowledged:
            return format_html('<span style="color: orange;">Acknowledged</span>')
        return format_html('<span style="color: red; font-weight: bold;">&#9888; Active</span>')

    status_indicator.short_description = "Status"

    def acknowledge_alerts(self, request, queryset):
        updated = 0
        for alert in queryset.filter(is_acknowledged=False):
            alert.is_acknowledged = True
            alert.acknowledged_by = request.user
            alert.acknowledged_at = timezone.now()
            alert.save(update_fields=["is_acknowledged", "acknowledged_by", "acknowledged_at"])
            updated += 1
        self.message_user(request, f"{updated} alerts acknowledged.")

    acknowledge_alerts.short_description = "Acknowledge selected alerts"

    def resolve_alerts(self, request, queryset):
        updated = 0
        for alert in queryset.filter(is_resolved=False):
            alert.is_resolved = True
            update_fields = ["is_resolved"]
            if not alert.is_acknowledged:
                alert.is_acknowledged = True
                alert.acknowledged_by = request.user
                alert.acknowledged_at = timezone.now()
                update_fields.extend(["is_acknowledged", "acknowledged_by", "acknowledged_at"])
            alert.save(update_fields=update_fields)
            updated += 1
        self.message_user(request, f"{updated} alerts marked as resolved.")

    resolve_alerts.short_description = "Mark as Resolved"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "checkout",
            "gps_location",
            "acknowledged_by",
        )
