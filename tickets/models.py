import random
import string
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import Department
from assets.models import Asset, Location


def generate_ticket_id():
    """Generate unique ticket ID (e.g., TKT-2026-ABC123)."""
    year = timezone.now().year
    random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"TKT-{year}-{random_part}"


class FaultTicket(models.Model):
    """
    ICT help desk ticket covering both asset faults and general support requests.
    """

    STATUS_OPEN = "OPEN"
    STATUS_TRIAGED = "TRIAGED"
    STATUS_ASSIGNED = "ASSIGNED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_PENDING_USER = "PENDING_USER"
    STATUS_PENDING_PARTS = "PENDING_PARTS"
    STATUS_RESOLVED = "RESOLVED"
    STATUS_CLOSED = "CLOSED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_TRIAGED, "Triaged"),
        (STATUS_ASSIGNED, "Assigned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_PENDING_USER, "Pending User"),
        (STATUS_PENDING_PARTS, "Pending Parts"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    OPEN_STATUSES = (
        STATUS_OPEN,
        STATUS_TRIAGED,
        STATUS_ASSIGNED,
        STATUS_IN_PROGRESS,
        STATUS_PENDING_USER,
        STATUS_PENDING_PARTS,
    )

    ACTIVE_WORK_STATUSES = (
        STATUS_ASSIGNED,
        STATUS_IN_PROGRESS,
        STATUS_PENDING_USER,
        STATUS_PENDING_PARTS,
    )

    PRIORITY_LOW = "LOW"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_HIGH = "HIGH"
    PRIORITY_CRITICAL = "CRITICAL"

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
        (PRIORITY_CRITICAL, "Critical"),
    ]

    IMPACT_SINGLE_USER = "SINGLE_USER"
    IMPACT_DEPARTMENT = "DEPARTMENT"
    IMPACT_ORGANIZATION_WIDE = "ORGANIZATION_WIDE"

    IMPACT_CHOICES = [
        (IMPACT_SINGLE_USER, "Single User"),
        (IMPACT_DEPARTMENT, "Department"),
        (IMPACT_ORGANIZATION_WIDE, "Organization Wide"),
    ]

    CATEGORY_HARDWARE = "HARDWARE"
    CATEGORY_SOFTWARE = "SOFTWARE"
    CATEGORY_ACCOUNT = "ACCOUNT"
    CATEGORY_NETWORK = "NETWORK"
    CATEGORY_REQUEST = "REQUEST"
    CATEGORY_OTHER = "OTHER"

    CATEGORY_CHOICES = [
        (CATEGORY_HARDWARE, "Hardware Fault"),
        (CATEGORY_SOFTWARE, "Software Problem"),
        (CATEGORY_ACCOUNT, "Account / Login"),
        (CATEGORY_NETWORK, "Network Complaint"),
        (CATEGORY_REQUEST, "ICT Service Request"),
        (CATEGORY_OTHER, "Other ICT Support"),
    ]

    SLA_HOURS_BY_PRIORITY = {
        PRIORITY_LOW: 120,
        PRIORITY_MEDIUM: 72,
        PRIORITY_HIGH: 24,
        PRIORITY_CRITICAL: 8,
    }

    RESPONSE_HOURS_BY_PRIORITY = {
        PRIORITY_LOW: 24,
        PRIORITY_MEDIUM: 8,
        PRIORITY_HIGH: 4,
        PRIORITY_CRITICAL: 1,
    }

    ticket_id = models.CharField(
        max_length=50,
        unique=True,
        default=generate_ticket_id,
        editable=False,
    )
    title = models.CharField(max_length=300)
    description = models.TextField()
    ticket_category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHER,
    )
    is_asset_fault = models.BooleanField(default=False)

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="tickets",
        null=True,
        blank=True,
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        related_name="tickets",
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="tickets",
    )

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_tickets",
    )
    triaged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triaged_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
    )
    impact = models.CharField(
        max_length=30,
        choices=IMPACT_CHOICES,
        default=IMPACT_SINGLE_USER,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    requires_maintenance = models.BooleanField(default=False)
    escalated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    triaged_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    resolution_notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Fault Ticket"
        verbose_name_plural = "Fault Tickets"
        indexes = [
            models.Index(fields=["ticket_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["due_date"]),
            models.Index(fields=["ticket_category"]),
        ]

    def __str__(self):
        return f"{self.ticket_id} - {self.title}"

    def clean(self):
        super().clean()

        if self.is_asset_fault and not self.asset_id:
            raise ValidationError(
                {"asset": "Select an asset for asset fault tickets or uncheck asset fault."}
            )

        if self.asset_id and self.department_id and self.asset.department_id:
            if self.asset.department_id != self.department_id:
                raise ValidationError(
                    {"asset": "Selected asset belongs to a different department than the ticket."}
                )

        if self.ticket_category == self.CATEGORY_HARDWARE and not self.is_asset_fault:
            self.is_asset_fault = True

    def _target_due_date(self):
        baseline = self.created_at or timezone.now()
        return baseline + timedelta(hours=self.SLA_HOURS_BY_PRIORITY.get(self.priority, 72))

    @property
    def response_due_at(self):
        baseline = self.created_at or timezone.now()
        return baseline + timedelta(hours=self.RESPONSE_HOURS_BY_PRIORITY.get(self.priority, 8))

    @property
    def resolution_time(self):
        if self.resolved_at:
            return self.resolved_at - self.created_at
        return None

    @property
    def response_time(self):
        if self.first_response_at:
            return self.first_response_at - self.created_at
        return None

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_overdue(self):
        if not self.is_open or not self.due_date:
            return False
        return timezone.now() > self.due_date

    @property
    def can_create_maintenance(self):
        return bool(self.asset_id and (self.is_asset_fault or self.requires_maintenance))

    def mark_first_response(self, when=None):
        if not self.first_response_at:
            self.first_response_at = when or timezone.now()

    def save(self, *args, **kwargs):
        self.full_clean()

        if self.asset_id and not self.location_id:
            self.location = self.asset.current_location

        if not self.due_date:
            self.due_date = self._target_due_date()

        now = timezone.now()
        if self.pk:
            old_ticket = FaultTicket.objects.get(pk=self.pk)

            if (
                old_ticket.status != self.status
                or old_ticket.assigned_to_id != self.assigned_to_id
                or old_ticket.triaged_by_id != self.triaged_by_id
            ):
                if self.triaged_by_id and not self.triaged_at:
                    self.triaged_at = now

                if self.status != self.STATUS_OPEN and not self.first_response_at:
                    self.first_response_at = now

                if self.assigned_to_id and self.status in self.ACTIVE_WORK_STATUSES and not self.assigned_at:
                    self.assigned_at = now

                if self.status == self.STATUS_RESOLVED and not self.resolved_at:
                    self.resolved_at = now

                if self.status == self.STATUS_CLOSED and not self.closed_at:
                    self.closed_at = now
        else:
            if self.triaged_by_id and not self.triaged_at:
                self.triaged_at = now
            if self.status != self.STATUS_OPEN and not self.first_response_at:
                self.first_response_at = now
            if self.assigned_to_id and self.status in self.ACTIVE_WORK_STATUSES and not self.assigned_at:
                self.assigned_at = now

        super().save(*args, **kwargs)


class TicketResolution(models.Model):
    ticket = models.OneToOneField(
        FaultTicket,
        on_delete=models.CASCADE,
        related_name="resolution",
    )
    resolution_summary = models.TextField()
    root_cause = models.TextField(blank=True)
    action_taken = models.TextField()
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ticket_resolutions",
    )
    resolved_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-resolved_at", "-id"]
        verbose_name = "Ticket Resolution"
        verbose_name_plural = "Ticket Resolutions"

    def __str__(self):
        return f"Resolution for {self.ticket.ticket_id}"


class TicketComment(models.Model):
    """
    Comments/updates on fault tickets.
    """

    ticket = models.ForeignKey(
        FaultTicket,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Ticket Comment"
        verbose_name_plural = "Ticket Comments"

    def __str__(self):
        return f"Comment on {self.ticket.ticket_id} by {self.user}"


class TicketAttachment(models.Model):
    """
    File attachments for help desk tickets (photos, screenshots, documents).
    """

    ticket = models.ForeignKey(
        FaultTicket,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="tickets/attachments/")
    description = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Ticket Attachment"
        verbose_name_plural = "Ticket Attachments"

    def __str__(self):
        return f"Attachment for {self.ticket.ticket_id}"
