from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    Asset,
    AssetActivityLog,
    AssetAssignment,
    AssetAttribute,
    AssetAttributeValue,
    AssetAudit,
    AssetAuditItem,
    AssetCategory,
    AssetDepreciation,
    AssetLocationHistory,
    AssetPurchase,
    AssetType,
    InstalledSoftware,
    Location,
    MaintenanceRecord,
    Software,
    Supplier,
)


class AssetLocationHistoryInline(admin.TabularInline):
    model = AssetLocationHistory
    extra = 0
    autocomplete_fields = ("location", "moved_by")
    fields = ("location", "moved_by", "moved_at", "notes")
    ordering = ("-moved_at",)


class AssetAssignmentInline(admin.TabularInline):
    model = AssetAssignment
    extra = 0
    autocomplete_fields = ("issued_by",)
    fields = (
        "assignee_identifier",
        "assignee_name",
        "assignee_contact",
        "assigned_date",
        "expected_return",
        "returned_date",
        "issued_by",
        "purpose",
        "condition_at_issue",
        "condition_at_return",
        "notes",
    )
    ordering = ("-assigned_date",)


class MaintenanceRecordInline(admin.TabularInline):
    model = MaintenanceRecord
    extra = 0
    fields = ("maintenance_type", "status", "start_date", "end_date", "technician", "cost")
    ordering = ("-start_date",)


class InstalledSoftwareInline(admin.TabularInline):
    model = InstalledSoftware
    extra = 0
    autocomplete_fields = ("software", "installed_by")
    fields = ("software", "installed_date", "installed_by", "notes")
    ordering = ("software__name",)


class AssetAttributeValueInline(admin.TabularInline):
    model = AssetAttributeValue
    extra = 0
    autocomplete_fields = ("attribute",)
    fields = ("attribute", "value")
    ordering = ("attribute__name",)


class AssetActivityLogInline(admin.TabularInline):
    model = AssetActivityLog
    extra = 0
    can_delete = False
    fields = ("action", "performed_by", "timestamp", "description")
    readonly_fields = ("action", "performed_by", "timestamp", "description")
    ordering = ("-timestamp",)

    def has_add_permission(self, request, obj=None):
        return False


class AssetDepreciationInline(admin.TabularInline):
    model = AssetDepreciation
    extra = 0
    max_num = 1
    fields = (
        "purchase_cost",
        "useful_life_years",
        "salvage_value",
        "depreciation_method",
        "start_date",
    )


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "type_count", "asset_count", "computer_category")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            type_total=Count("types", distinct=True),
            asset_total=Count("assets", distinct=True),
        ).ordered_choices()

    @admin.display(ordering="type_total", description="Types")
    def type_count(self, obj):
        return obj.type_total

    @admin.display(ordering="asset_total", description="Assets")
    def asset_count(self, obj):
        return obj.asset_total

    @admin.display(boolean=True, description="Computer Category")
    def computer_category(self, obj):
        return obj.is_computer_category


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "asset_count")
    list_filter = ("category",)
    search_fields = ("name", "category__name")
    autocomplete_fields = ("category",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("category").annotate(
            asset_total=Count("assets", distinct=True)
        )

    @admin.display(ordering="asset_total", description="Assets")
    def asset_count(self, obj):
        return obj.asset_total


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_email", "phone", "purchase_count")
    search_fields = ("name", "contact_email", "phone")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(purchase_total=Count("purchases", distinct=True))

    @admin.display(ordering="purchase_total", description="Purchases")
    def purchase_count(self, obj):
        return obj.purchase_total


@admin.register(AssetPurchase)
class AssetPurchaseAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "supplier", "purchase_date", "total_cost", "asset_count")
    list_filter = ("purchase_date", "supplier")
    search_fields = ("purchase_order", "invoice_number", "supplier__name")
    autocomplete_fields = ("supplier",)
    date_hierarchy = "purchase_date"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("supplier").annotate(
            asset_total=Count("assets", distinct=True)
        )

    @admin.display(ordering="asset_total", description="Assets")
    def asset_count(self, obj):
        return obj.asset_total


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "asset_tag",
        "name",
        "category",
        "asset_type",
        "department",
        "status_badge",
        "assigned_to_display",
        "current_location_display",
        "current_value_display",
        "is_active",
    )
    list_filter = ("status", "is_active", "category", "asset_type", "department")
    search_fields = ("asset_tag", "name", "serial_number")
    autocomplete_fields = ("category", "asset_type", "department", "purchase")
    list_select_related = ("category", "asset_type", "department", "purchase")
    readonly_fields = (
        "created_at",
        "updated_at",
        "current_location_display",
        "assigned_to_display",
        "current_value_display",
    )
    fieldsets = (
        (
            "Asset Details",
            {
                "fields": (
                    "asset_tag",
                    "name",
                    "category",
                    "asset_type",
                    "serial_number",
                    "status",
                    "is_active",
                )
            },
        ),
        (
            "Ownership And Procurement",
            {
                "fields": (
                    "department",
                    "purchase",
                    "purchase_date",
                    "purchase_cost",
                    "warranty_expiry",
                )
            },
        ),
        (
            "Current Snapshot",
            {
                "fields": (
                    "assigned_to_display",
                    "current_location_display",
                    "current_value_display",
                )
            },
        ),
        ("System Fields", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    inlines = (
        AssetDepreciationInline,
        AssetAssignmentInline,
        AssetLocationHistoryInline,
        MaintenanceRecordInline,
        InstalledSoftwareInline,
        AssetAttributeValueInline,
        AssetActivityLogInline,
    )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        colors = {
            Asset.STATUS_AVAILABLE: "#1f7a1f",
            Asset.STATUS_ASSIGNED: "#004b8d",
            Asset.STATUS_MAINTENANCE: "#a65d00",
            Asset.STATUS_RESERVED: "#6b3fa0",
            Asset.STATUS_RETIRED: "#5a5a5a",
            Asset.STATUS_LOST: "#a40000",
        }
        label = obj.get_status_display()
        color = colors.get(obj.status, "#5a5a5a")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:999px;">{}</span>',
            color,
            label,
        )

    @admin.display(description="Assigned To")
    def assigned_to_display(self, obj):
        assignment = obj.current_assignment
        if not assignment:
            return "-"
        return assignment.assignee_display

    @admin.display(description="Current Location")
    def current_location_display(self, obj):
        return obj.current_location or "-"

    @admin.display(description="Current Value")
    def current_value_display(self, obj):
        if obj.current_value is None:
            return "-"
        return f"{obj.current_value:,.2f}"


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "building", "room", "asset_moves")
    list_filter = ("building",)
    search_fields = ("name", "building", "room")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(move_total=Count("asset_history", distinct=True))

    @admin.display(ordering="move_total", description="Recorded Moves")
    def asset_moves(self, obj):
        return obj.move_total


@admin.register(AssetLocationHistory)
class AssetLocationHistoryAdmin(admin.ModelAdmin):
    list_display = ("asset", "location", "moved_by", "moved_at")
    list_filter = ("location", "moved_at")
    search_fields = ("asset__asset_tag", "asset__name", "location__name", "notes")
    autocomplete_fields = ("asset", "location", "moved_by")
    date_hierarchy = "moved_at"


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "assignee_name",
        "assignee_identifier",
        "assignee_contact",
        "purpose",
        "assigned_date",
        "expected_return",
        "returned_date",
        "assignment_state",
    )
    list_filter = ("assigned_date", "returned_date")
    search_fields = (
        "asset__asset_tag",
        "asset__name",
        "assignee_identifier",
        "assignee_name",
        "assignee_contact",
        "purpose",
        "condition_at_issue",
        "condition_at_return",
    )
    autocomplete_fields = ("asset", "issued_by")
    date_hierarchy = "assigned_date"

    @admin.display(boolean=True, description="Active")
    def assignment_state(self, obj):
        return obj.is_active


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("asset", "maintenance_type", "status", "start_date", "end_date", "technician", "cost")
    list_filter = ("maintenance_type", "status", "start_date")
    search_fields = ("asset__asset_tag", "asset__name", "issue_description", "technician")
    autocomplete_fields = ("asset",)
    date_hierarchy = "start_date"


@admin.register(Software)
class SoftwareAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "vendor", "installation_count")
    list_filter = ("vendor",)
    search_fields = ("name", "version", "vendor")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            installation_total=Count("installations", distinct=True)
        )

    @admin.display(ordering="installation_total", description="Installations")
    def installation_count(self, obj):
        return obj.installation_total


@admin.register(InstalledSoftware)
class InstalledSoftwareAdmin(admin.ModelAdmin):
    list_display = ("asset", "software", "installed_date", "installed_by")
    list_filter = ("installed_date", "software")
    search_fields = ("asset__asset_tag", "asset__name", "software__name", "software__version")
    autocomplete_fields = ("asset", "software", "installed_by")
    date_hierarchy = "installed_date"


@admin.register(AssetAttribute)
class AssetAttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "field_type", "required")
    list_filter = ("category", "field_type", "required")
    search_fields = ("name", "category__name", "help_text")
    autocomplete_fields = ("category",)


@admin.register(AssetAttributeValue)
class AssetAttributeValueAdmin(admin.ModelAdmin):
    list_display = ("asset", "attribute", "short_value")
    list_filter = ("attribute__category", "attribute")
    search_fields = ("asset__asset_tag", "asset__name", "attribute__name", "value")
    autocomplete_fields = ("asset", "attribute")

    @admin.display(description="Value")
    def short_value(self, obj):
        if len(obj.value) <= 60:
            return obj.value
        return f"{obj.value[:57]}..."


@admin.register(AssetDepreciation)
class AssetDepreciationAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "purchase_cost",
        "useful_life_years",
        "salvage_value",
        "depreciation_method",
        "current_value_display",
    )
    list_filter = ("depreciation_method",)
    search_fields = ("asset__asset_tag", "asset__name")
    autocomplete_fields = ("asset",)

    @admin.display(description="Current Value")
    def current_value_display(self, obj):
        return f"{obj.current_value:,.2f}"


class AssetAuditItemInline(admin.TabularInline):
    model = AssetAuditItem
    extra = 0
    autocomplete_fields = ("asset",)
    fields = ("asset", "status", "notes")


@admin.register(AssetAudit)
class AssetAuditAdmin(admin.ModelAdmin):
    list_display = ("audit_date", "conducted_by", "item_count")
    list_filter = ("audit_date",)
    search_fields = ("notes", "conducted_by__email", "conducted_by__first_name", "conducted_by__last_name")
    autocomplete_fields = ("conducted_by",)
    date_hierarchy = "audit_date"
    inlines = (AssetAuditItemInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(item_total=Count("items", distinct=True))

    @admin.display(ordering="item_total", description="Items")
    def item_count(self, obj):
        return obj.item_total


@admin.register(AssetAuditItem)
class AssetAuditItemAdmin(admin.ModelAdmin):
    list_display = ("audit", "asset", "status")
    list_filter = ("status", "audit__audit_date")
    search_fields = ("audit__notes", "asset__asset_tag", "asset__name", "notes")
    autocomplete_fields = ("audit", "asset")


@admin.register(AssetActivityLog)
class AssetActivityLogAdmin(admin.ModelAdmin):
    list_display = ("asset", "action", "performed_by", "timestamp")
    list_filter = ("timestamp",)
    search_fields = ("asset__asset_tag", "asset__name", "action", "description")
    autocomplete_fields = ("asset", "performed_by")
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False
