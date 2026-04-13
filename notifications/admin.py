from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Alert, Notification, SMSNotificationLog


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "user",
        "notification_type",
        "read_status",
        "created_at",
    )
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("title", "message", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "read_at")
    date_hierarchy = "created_at"
    list_per_page = 25
    actions = ["mark_as_read"]

    def read_status(self, obj):
        if obj.is_read:
            return format_html('<span style="color: green;">&#10003; Read</span>')
        return format_html('<span style="color: orange;">Pending</span>')

    read_status.short_description = "Read Status"

    def mark_as_read(self, request, queryset):
        updated = 0
        for notification in queryset.filter(is_read=False):
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
            updated += 1
        self.message_user(request, f"{updated} notifications marked as read.")

    mark_as_read.short_description = "Mark selected notifications as read"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "severity_badge",
        "asset",
        "acknowledgement_status",
        "created_at",
    )
    list_filter = ("severity", "is_acknowledged", "created_at")
    search_fields = ("title", "message", "asset__asset_tag", "asset__name")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    list_per_page = 25
    actions = ["acknowledge_alerts"]

    def severity_badge(self, obj):
        colors = {
            "INFO": "#17a2b8",
            "WARNING": "#ffc107",
            "CRITICAL": "#dc3545",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.severity, "#17a2b8"),
            obj.get_severity_display(),
        )

    severity_badge.short_description = "Severity"

    def acknowledgement_status(self, obj):
        if obj.is_acknowledged:
            return format_html('<span style="color: green;">&#10003; Acknowledged</span>')
        return format_html('<span style="color: red; font-weight: bold;">&#9888; Active</span>')

    acknowledgement_status.short_description = "Status"

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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("asset", "acknowledged_by")


@admin.register(SMSNotificationLog)
class SMSNotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "phone_number",
        "recipient",
        "status",
        "provider_message_id",
        "notification_date",
        "created_at",
    )
    list_filter = ("event_type", "status", "notification_date", "created_at")
    search_fields = (
        "phone_number",
        "message",
        "provider_message_id",
        "recipient__email",
        "recipient__first_name",
        "recipient__last_name",
        "error_message",
    )
    readonly_fields = (
        "event_type",
        "content_type",
        "object_id",
        "recipient",
        "phone_number",
        "message",
        "status",
        "provider_message_id",
        "provider_response",
        "error_message",
        "notification_date",
        "created_at",
    )
    list_select_related = ("recipient", "content_type")
    date_hierarchy = "created_at"
