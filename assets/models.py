from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from accounts.models import Department


ASSET_CATEGORY_COMPUTERS = "Computers"
ASSET_CATEGORY_NETWORKING = "Networking"
ASSET_CATEGORY_FURNITURE = "Furniture"
ASSET_CATEGORY_PRINTERS = "Printers"
ASSET_CATEGORY_CONSUMABLES = "Consumables"
ASSET_CATEGORY_PROJECTORS = "Projectors"
ASSET_CATEGORY_OTHERS = "Others"

ASSET_CATEGORY_NAMES = (
    ASSET_CATEGORY_COMPUTERS,
    ASSET_CATEGORY_NETWORKING,
    ASSET_CATEGORY_FURNITURE,
    ASSET_CATEGORY_PRINTERS,
    ASSET_CATEGORY_CONSUMABLES,
    ASSET_CATEGORY_PROJECTORS,
    ASSET_CATEGORY_OTHERS,
)

ASSET_CATEGORY_CHOICES = tuple((name, name) for name in ASSET_CATEGORY_NAMES)


# Begin AssetCategoryQuerySet class
class AssetCategoryQuerySet(models.QuerySet):
    def ordered_choices(self):
        return self.order_by(
            Case(
                *[
                    When(name=name, then=Value(index))
                    for index, name in enumerate(ASSET_CATEGORY_NAMES)
                ],
                default=Value(len(ASSET_CATEGORY_NAMES)),
                output_field=IntegerField(),
            ),
            "name",
        )
# End AssetCategoryQuerySet class


# Begin AssetCategory model
class AssetCategory(models.Model):
    objects = AssetCategoryQuerySet.as_manager()

    name = models.CharField(
        max_length=100,
        unique=True,
        choices=ASSET_CATEGORY_CHOICES,
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Asset Category"
        verbose_name_plural = "Asset Categories"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.name and self.name not in dict(ASSET_CATEGORY_CHOICES):
            raise ValidationError(
                {
                    "name": (
                        "Category must be one of: "
                        + ", ".join(ASSET_CATEGORY_NAMES)
                        + "."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_computer_category(self):
        return self.name == ASSET_CATEGORY_COMPUTERS
# End AssetCategory model


# Begin AssetType model
class AssetType(models.Model):
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.CASCADE,
        related_name="types",
    )
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["category__name", "name"]
        unique_together = ("category", "name")

    def __str__(self):
        return f"{self.category.name} - {self.name}"
# End AssetType model


# Begin Supplier model
class Supplier(models.Model):
    name = models.CharField(max_length=150, unique=True)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
# End Supplier model


# Begin AssetPurchase model
class AssetPurchase(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchases",
    )
    purchase_order = models.CharField(max_length=100)
    invoice_number = models.CharField(max_length=100, blank=True)
    purchase_date = models.DateField()
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["-purchase_date", "-id"]

    def __str__(self):
        return f"PO {self.purchase_order}"
# End AssetPurchase model


# Begin Asset model
class Asset(models.Model):
    STATUS_AVAILABLE = "available"
    STATUS_ASSIGNED = "assigned"
    STATUS_MAINTENANCE = "maintenance"
    STATUS_RESERVED = "reserved"
    STATUS_RETIRED = "retired"
    STATUS_LOST = "lost"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_ASSIGNED, "Assigned"),
        (STATUS_MAINTENANCE, "Maintenance"),
        (STATUS_RESERVED, "Reserved"),
        (STATUS_RETIRED, "Retired"),
        (STATUS_LOST, "Lost"),
    ]

    asset_tag = models.CharField(max_length=50, unique=True, null=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    serial_number = models.CharField(max_length=200, blank=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    purchase = models.ForeignKey(
        AssetPurchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    warranty_expiry = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_AVAILABLE,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_tag"]

    def __str__(self):
        return f"{self.asset_tag} - {self.name}"

    def clean(self):
        if self.asset_type_id and self.category_id:
            if self.asset_type.category_id != self.category_id:
                raise ValidationError(
                    {"asset_type": "Selected asset type does not belong to the selected category."}
                )

    @property
    def current_assignment(self):
        return self.assignments.filter(returned_date__isnull=True).order_by("-assigned_date").first()

    @property
    def current_location_record(self):
        return self.location_history.order_by("-moved_at", "-pk").first()

    @property
    def current_location(self):
        record = self.current_location_record
        return record.location if record else None

    @property
    def current_value(self):
        if hasattr(self, "depreciation"):
            return self.depreciation.current_value
        return None

    @property
    def is_computer(self):
        return bool(self.category_id and self.category.is_computer_category)
# End Asset model


# Begin Location model
class Location(models.Model):
    name = models.CharField(max_length=150)
    building = models.CharField(max_length=150, blank=True)
    room = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "building", "room"]
        unique_together = ("name", "building", "room")

    def __str__(self):
        parts = [self.name]
        if self.building:
            parts.append(self.building)
        if self.room:
            parts.append(f"Room {self.room}")
        return " - ".join(parts)
# End Location model


# Begin AssetLocationHistory model
class AssetLocationHistory(models.Model):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="location_history",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="asset_history",
    )
    moved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_moves",
    )
    moved_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-moved_at"]

    def __str__(self):
        return f"{self.asset.asset_tag} -> {self.location}"
# End AssetLocationHistory model


# Begin AssetAssignment model
class AssetAssignment(models.Model):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_assignments",
    )
    assignee_identifier = models.CharField(max_length=100, blank=True)
    assignee_name = models.CharField(max_length=200, blank=True)
    assignee_contact = models.CharField(max_length=100, blank=True)
    assigned_date = models.DateField()
    expected_return = models.DateField(null=True, blank=True)
    returned_date = models.DateField(null=True, blank=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_asset_assignments",
    )
    purpose = models.CharField(max_length=255, blank=True)
    condition_at_issue = models.CharField(max_length=100, blank=True)
    condition_at_return = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-assigned_date"]

    def __str__(self):
        return f"{self.asset.asset_tag} assigned to {self.assignee_display}"

    @property
    def assignee_display(self):
        if self.assignee_name:
            return self.assignee_name
        if self.user_id:
            return self.user.get_full_name() or self.user.email
        return "Unknown assignee"

    @property
    def is_active(self):
        return self.returned_date is None

    def clean(self):
        if self.user_id and not self.assignee_identifier:
            self.assignee_identifier = str(self.user_id)
        if self.user_id and not self.assignee_name:
            self.assignee_name = self.user.get_full_name() or self.user.email
        if self.user_id and not self.assignee_contact:
            self.assignee_contact = self.user.email

        missing_fields = []
        if not self.assignee_identifier:
            missing_fields.append("assignee_identifier")
        if not self.assignee_name:
            missing_fields.append("assignee_name")
        if not self.assignee_contact:
            missing_fields.append("assignee_contact")
        if missing_fields:
            raise ValidationError(
                {
                    field: "This field is required."
                    for field in missing_fields
                }
            )
        if self.returned_date and self.returned_date < self.assigned_date:
            raise ValidationError({"returned_date": "Returned date cannot be earlier than assigned date."})
# End AssetAssignment model


# Begin MaintenanceRecord model
class MaintenanceRecord(models.Model):
    TYPE_REPAIR = "repair"
    TYPE_UPGRADE = "upgrade"
    TYPE_INSPECTION = "inspection"

    TYPE_CHOICES = [
        (TYPE_REPAIR, "Repair"),
        (TYPE_UPGRADE, "Upgrade"),
        (TYPE_INSPECTION, "Inspection"),
    ]

    STATUS_OPEN = "open"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
    ]

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="maintenance_records",
    )
    issue_description = models.TextField()
    maintenance_type = models.CharField(max_length=100, choices=TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    technician = models.CharField(max_length=150, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_OPEN)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.get_maintenance_type_display()}"

    @property
    def is_open(self):
        return self.status in {self.STATUS_OPEN, self.STATUS_IN_PROGRESS}

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be earlier than start date."})
# End MaintenanceRecord model


# Begin Software model
class Software(models.Model):
    name = models.CharField(max_length=150)
    version = models.CharField(max_length=100, blank=True)
    vendor = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["name", "version"]
        unique_together = ("name", "version", "vendor")

    def __str__(self):
        base = self.name
        if self.version:
            base = f"{base} {self.version}"
        return base
# End Software model


# Begin InstalledSoftware model
class InstalledSoftware(models.Model):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="installed_software",
    )
    software = models.ForeignKey(
        Software,
        on_delete=models.CASCADE,
        related_name="installations",
    )
    installed_date = models.DateField(null=True, blank=True)
    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="software_installations",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["asset__asset_tag", "software__name"]
        unique_together = ("asset", "software")

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.software}"

    def clean(self):
        if self.asset_id and not self.asset.is_computer:
            raise ValidationError("Software can only be recorded for computer assets.")
# End InstalledSoftware model


# Begin AssetAttribute model
class AssetAttribute(models.Model):
    FIELD_TEXT = "text"
    FIELD_NUMBER = "number"
    FIELD_DATE = "date"
    FIELD_BOOLEAN = "boolean"

    FIELD_TYPE_CHOICES = [
        (FIELD_TEXT, "Text"),
        (FIELD_NUMBER, "Number"),
        (FIELD_DATE, "Date"),
        (FIELD_BOOLEAN, "Boolean"),
    ]

    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.CASCADE,
        related_name="attributes",
    )
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default=FIELD_TEXT)
    required = models.BooleanField(default=False)
    help_text = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["category__name", "name"]
        unique_together = ("category", "name")

    def __str__(self):
        return f"{self.category.name} - {self.name}"
# End AssetAttribute model


# Begin AssetAttributeValue model
class AssetAttributeValue(models.Model):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )
    attribute = models.ForeignKey(
        AssetAttribute,
        on_delete=models.CASCADE,
        related_name="values",
    )
    value = models.TextField()

    class Meta:
        ordering = ["attribute__name"]
        unique_together = ("asset", "attribute")

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.attribute.name}"

    def clean(self):
        if self.asset_id and self.attribute_id:
            if self.asset.category_id != self.attribute.category_id:
                raise ValidationError(
                    {"attribute": "This attribute does not belong to the asset category."}
                )
# End AssetAttributeValue model


# Begin AssetDepreciation model
class AssetDepreciation(models.Model):
    METHOD_STRAIGHT_LINE = "straight_line"

    METHOD_CHOICES = [
        (METHOD_STRAIGHT_LINE, "Straight Line"),
    ]

    asset = models.OneToOneField(
        Asset,
        on_delete=models.CASCADE,
        related_name="depreciation",
    )
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2)
    useful_life_years = models.PositiveIntegerField()
    salvage_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    depreciation_method = models.CharField(
        max_length=50,
        choices=METHOD_CHOICES,
        default=METHOD_STRAIGHT_LINE,
    )
    start_date = models.DateField()

    class Meta:
        ordering = ["asset__asset_tag"]

    def __str__(self):
        return f"Depreciation - {self.asset.asset_tag}"

    def clean(self):
        if self.salvage_value > self.purchase_cost:
            raise ValidationError({"salvage_value": "Salvage value cannot exceed purchase cost."})
        if self.useful_life_years < 1:
            raise ValidationError({"useful_life_years": "Useful life must be at least 1 year."})

    @property
    def annual_depreciation(self):
        depreciable_amount = self.purchase_cost - self.salvage_value
        return depreciable_amount / Decimal(self.useful_life_years)

    @property
    def years_used(self):
        today = date.today()
        years = today.year - self.start_date.year
        if (today.month, today.day) < (self.start_date.month, self.start_date.day):
            years -= 1
        return max(years, 0)

    @property
    def accumulated_depreciation(self):
        amount = self.annual_depreciation * Decimal(self.years_used)
        max_allowed = self.purchase_cost - self.salvage_value
        return min(amount, max_allowed)

    @property
    def current_value(self):
        current = self.purchase_cost - self.accumulated_depreciation
        return max(current, self.salvage_value)
# End AssetDepreciation model


# Begin AssetAudit model
class AssetAudit(models.Model):
    audit_date = models.DateField()
    conducted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_audits_conducted",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-audit_date", "-id"]

    def __str__(self):
        return f"Audit {self.audit_date}"
# End AssetAudit model


# Begin AssetAuditItem model
class AssetAuditItem(models.Model):
    STATUS_FOUND = "found"
    STATUS_MISSING = "missing"
    STATUS_DAMAGED = "damaged"
    STATUS_RELOCATED = "relocated"

    STATUS_CHOICES = [
        (STATUS_FOUND, "Found"),
        (STATUS_MISSING, "Missing"),
        (STATUS_DAMAGED, "Damaged"),
        (STATUS_RELOCATED, "Relocated"),
    ]

    audit = models.ForeignKey(
        AssetAudit,
        on_delete=models.CASCADE,
        related_name="items",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="audit_items",
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["asset__asset_tag"]
        unique_together = ("audit", "asset")

    def __str__(self):
        return f"{self.audit} - {self.asset.asset_tag}"
# End AssetAuditItem model


# Begin AssetActivityLog model
class AssetActivityLog(models.Model):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=200)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_activity_logs",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.asset.asset_tag} - {self.action}"
# End AssetActivityLog model
