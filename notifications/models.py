from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ("SYSTEM", "System"),
        ("ALERT", "Alert"),
        ("REMINDER", "Reminder"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        default="SYSTEM",
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.title} -> {self.user}"


class Alert(models.Model):
    SEVERITY_CHOICES = [
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("CRITICAL", "Critical"),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="INFO")
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="alerts",
        null=True,
        blank=True,
    )
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acknowledged_alerts",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Alert"
        verbose_name_plural = "Alerts"
        indexes = [
            models.Index(fields=["severity", "is_acknowledged"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.title


class SMSNotificationLog(models.Model):
    STATUS_SENT = "SENT"
    STATUS_FAILED = "FAILED"
    STATUS_SKIPPED = "SKIPPED"

    STATUS_CHOICES = [
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    EVENT_TICKET_CREATED = "TICKET_CREATED"
    EVENT_TICKET_ASSIGNED = "TICKET_ASSIGNED"
    EVENT_ASSIGNMENT_OVERDUE = "ASSIGNMENT_OVERDUE"

    EVENT_CHOICES = [
        (EVENT_TICKET_CREATED, "Ticket Created"),
        (EVENT_TICKET_ASSIGNED, "Ticket Assigned"),
        (EVENT_ASSIGNMENT_OVERDUE, "Assignment Overdue"),
    ]

    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_notification_logs",
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sms_notification_logs",
    )
    phone_number = models.CharField(max_length=32)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    provider_message_id = models.CharField(max_length=100, blank=True)
    provider_response = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    notification_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "SMS Notification Log"
        verbose_name_plural = "SMS Notification Logs"
        indexes = [
            models.Index(fields=["event_type", "notification_date"]),
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["phone_number", "notification_date"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} -> {self.phone_number} ({self.status})"
