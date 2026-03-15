from django.db import models
from django.conf import settings
from django.utils import timezone

from assets.models import Asset


class MaintenanceLog(models.Model):
    MAINTENANCE_TYPE_CHOICES = [
        ("PREVENTIVE", "Preventive Maintenance"),
        ("CORRECTIVE", "Corrective Maintenance"),
        ("INSPECTION", "Inspection"),
        ("UPGRADE", "Upgrade"),
    ]
    STATUS_CHOICES = [
        ("IN_PROGRESS", "In Progress"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenance_logs")
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="IN_PROGRESS")
    description = models.TextField()

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_performed",
    )
    performed_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    parts_replaced = models.TextField(
        blank=True,
        null=True,
        help_text="List of replaced parts/components",
    )
    next_maintenance_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-performed_at"]
        verbose_name = "Maintenance Log"
        verbose_name_plural = "Maintenance Logs"
        indexes = [
            models.Index(fields=["asset"]),
            models.Index(fields=["performed_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.get_maintenance_type_display()} - {self.asset.asset_tag}"


class MaintenanceSchedule(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenance_schedules")
    title = models.CharField(max_length=200)
    description = models.TextField()

    scheduled_date = models.DateField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_maintenance",
    )
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_date"]
        verbose_name = "Maintenance Schedule"
        verbose_name_plural = "Maintenance Schedules"

    def __str__(self):
        return f"{self.title} - {self.asset.asset_tag} ({self.scheduled_date})"

    @property
    def is_overdue(self):
        if self.is_completed or not self.scheduled_date:
            return False
        return self.scheduled_date < timezone.localdate()



