from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import MaintenanceLog, MaintenanceSchedule


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "maintenance_type",
        "status_badge",
        "performed_by",
        "performed_at",
        "completed_at",
        "cost",
        "next_maintenance_date",
    )
    list_filter = (
        "maintenance_type",
        "status",
        "performed_at",
        "performed_by",
    )
    search_fields = (
        "asset__asset_tag",
        "asset__name",
        "description",
        "parts_replaced",
    )
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Asset & Type", {"fields": ("asset", "maintenance_type", "status")}),
        (
            "Details",
            {
                "fields": (
                    "description",
                    "parts_replaced",
                    "performed_by",
                    "performed_at",
                    "completed_at",
                )
            },
        ),
        ("Financial", {"fields": ("cost",)}),
        ("Follow-up", {"fields": ("next_maintenance_date", "notes")}),
        (
            "System Info",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    date_hierarchy = "performed_at"
    list_per_page = 25

    def status_badge(self, obj):
        colors = {
            "IN_PROGRESS": "orange",
            "COMPLETED": "green",
            "CANCELLED": "gray",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, "blue"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("asset", "performed_by")

    def save_model(self, request, obj, form, change):
        obj._changed_by = request.user
        if not obj.performed_by_id:
            obj.performed_by = request.user
        if obj.status == "COMPLETED" and not obj.completed_at:
            obj.completed_at = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "asset",
        "scheduled_date",
        "assigned_to",
        "status_badge",
        "overdue_indicator",
    )
    list_filter = (
        "is_completed",
        "scheduled_date",
        "assigned_to",
    )
    search_fields = (
        "title",
        "asset__asset_tag",
        "asset__name",
        "description",
    )

    readonly_fields = ("created_at", "updated_at", "overdue_indicator")
    fieldsets = (
        ("Schedule Information", {"fields": ("title", "asset", "description")}),
        ("Assignment", {"fields": ("scheduled_date", "assigned_to")}),
        ("Completion", {"fields": ("is_completed", "completed_at")}),
        (
            "System Info",
            {"fields": ("created_at", "updated_at", "overdue_indicator"), "classes": ("collapse",)},
        ),
    )
    date_hierarchy = "scheduled_date"
    list_per_page = 25
    actions = ["mark_completed"]

    def status_badge(self, obj):
        if obj.is_completed:
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 10px; border-radius: 3px;">&#10003; {}</span>',
                "Completed",
            )
        return format_html(
            '<span style="background-color: orange; color: white; padding: 3px 10px; border-radius: 3px;">&#9203; {}</span>',
            "Pending",
        )

    status_badge.short_description = "Status"

    def overdue_indicator(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">&#9888; {}</span>',
                "OVERDUE",
            )
        return format_html('<span style="color: green;">&#10003; {}</span>', "On Schedule")

    overdue_indicator.short_description = "Schedule Status"

    def mark_completed(self, request, queryset):
        updated = 0
        for schedule in queryset.filter(is_completed=False):
            schedule.is_completed = True
            schedule.completed_at = timezone.now()
            schedule.save()
            updated += 1
        self.message_user(request, f"{updated} schedules marked as completed.")

    mark_completed.short_description = "Mark as Completed"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("asset", "assigned_to")
