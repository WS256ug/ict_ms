from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.html import format_html

from .models import FaultTicket, TicketAttachment, TicketComment, TicketResolution


class TicketCommentInline(admin.TabularInline):
    model = TicketComment
    extra = 1
    readonly_fields = ("user", "created_at")
    fields = ("user", "comment", "created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user")


class TicketAttachmentInline(admin.TabularInline):
    model = TicketAttachment
    extra = 1
    readonly_fields = ("uploaded_by", "uploaded_at")
    fields = ("file", "description", "uploaded_by", "uploaded_at")


class TicketResolutionInline(admin.StackedInline):
    model = TicketResolution
    extra = 0
    max_num = 1
    fields = ("resolution_summary", "root_cause", "action_taken", "resolved_by", "resolved_at")


@admin.register(FaultTicket)
class FaultTicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_id",
        "title",
        "ticket_category",
        "department",
        "priority_badge",
        "status_badge",
        "impact",
        "reported_by",
        "triaged_by",
        "assigned_to",
        "due_date",
        "overdue_indicator",
        "created_at",
    )
    list_filter = (
        "status",
        "priority",
        "impact",
        "ticket_category",
        "is_asset_fault",
        "requires_maintenance",
        "escalated",
        "department",
        "created_at",
        "assigned_to",
    )
    search_fields = (
        "ticket_id",
        "title",
        "description",
        "asset__asset_tag",
        "asset__name",
        "reported_by__email",
        "assigned_to__email",
        "triaged_by__email",
    )
    readonly_fields = (
        "ticket_id",
        "created_at",
        "updated_at",
        "triaged_at",
        "first_response_at",
        "assigned_at",
        "resolved_at",
        "closed_at",
        "resolution_time_display",
        "overdue_indicator",
    )
    fieldsets = (
        (
            "Ticket Information",
            {
                "fields": (
                    "ticket_id",
                    "title",
                    "description",
                    "ticket_category",
                    "is_asset_fault",
                    "department",
                    "asset",
                    "location",
                )
            },
        ),
        ("Priority & Workflow", {"fields": ("priority", "impact", "status", "assigned_to", "due_date")}),
        ("Triage & Controls", {"fields": ("triaged_by", "requires_maintenance", "escalated", "resolution_notes")}),
        (
            "Timing",
            {
                "fields": (
                    "created_at",
                    "triaged_at",
                    "first_response_at",
                    "assigned_at",
                    "resolved_at",
                    "closed_at",
                    "updated_at",
                    "resolution_time_display",
                    "overdue_indicator",
                ),
                "classes": ("collapse",),
            },
        ),
    )
    inlines = [TicketResolutionInline, TicketCommentInline, TicketAttachmentInline]
    list_per_page = 25
    date_hierarchy = "created_at"
    actions = ["mark_triaged", "assign_to_me", "mark_in_progress", "mark_pending_user"]

    def priority_badge(self, obj):
        colors = {
            FaultTicket.PRIORITY_LOW: "#6c757d",
            FaultTicket.PRIORITY_MEDIUM: "#0dcaf0",
            FaultTicket.PRIORITY_HIGH: "#fd7e14",
            FaultTicket.PRIORITY_CRITICAL: "#dc3545",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.priority, "#6c757d"),
            obj.get_priority_display(),
        )

    priority_badge.short_description = "Priority"

    def status_badge(self, obj):
        colors = {
            FaultTicket.STATUS_OPEN: "#6c757d",
            FaultTicket.STATUS_TRIAGED: "#0d6efd",
            FaultTicket.STATUS_ASSIGNED: "#6610f2",
            FaultTicket.STATUS_IN_PROGRESS: "#ffc107",
            FaultTicket.STATUS_PENDING_USER: "#0dcaf0",
            FaultTicket.STATUS_PENDING_PARTS: "#fd7e14",
            FaultTicket.STATUS_RESOLVED: "#198754",
            FaultTicket.STATUS_CLOSED: "#212529",
            FaultTicket.STATUS_CANCELLED: "#dc3545",
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def overdue_indicator(self, obj):
        if obj.is_overdue:
            return format_html(
                '<span style="color: red; font-weight: bold;">&#9888; Overdue</span>'
            )
        return format_html('<span style="color: green;">&#10003; On Track</span>')

    overdue_indicator.short_description = "SLA Status"

    def resolution_time_display(self, obj):
        if obj.resolution_time:
            total_seconds = int(obj.resolution_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
        return "Not resolved yet"

    resolution_time_display.short_description = "Resolution Time"

    def mark_triaged(self, request, queryset):
        updated = 0
        for ticket in queryset.filter(status=FaultTicket.STATUS_OPEN):
            ticket.status = FaultTicket.STATUS_TRIAGED
            ticket.triaged_by = request.user
            ticket.save()
            updated += 1
        self.message_user(request, f"{updated} tickets marked as triaged.")

    mark_triaged.short_description = "Mark selected tickets as triaged"

    def assign_to_me(self, request, queryset):
        updated = 0
        for ticket in queryset.filter(
            Q(status=FaultTicket.STATUS_OPEN) | Q(status=FaultTicket.STATUS_TRIAGED)
        ):
            ticket.assigned_to = request.user
            ticket.status = FaultTicket.STATUS_ASSIGNED
            ticket.save()
            updated += 1
        self.message_user(request, f"{updated} tickets assigned to you.")

    assign_to_me.short_description = "Assign selected tickets to me"

    def mark_in_progress(self, request, queryset):
        updated = 0
        for ticket in queryset.filter(
            status__in=[FaultTicket.STATUS_ASSIGNED, FaultTicket.STATUS_TRIAGED]
        ):
            ticket.status = FaultTicket.STATUS_IN_PROGRESS
            ticket.save()
            updated += 1
        self.message_user(request, f"{updated} tickets marked as In Progress.")

    mark_in_progress.short_description = "Mark as In Progress"

    def mark_pending_user(self, request, queryset):
        updated = 0
        for ticket in queryset.filter(
            status__in=[FaultTicket.STATUS_ASSIGNED, FaultTicket.STATUS_IN_PROGRESS]
        ):
            ticket.status = FaultTicket.STATUS_PENDING_USER
            ticket.save()
            updated += 1
        self.message_user(request, f"{updated} tickets moved to Pending User.")

    mark_pending_user.short_description = "Mark as Pending User"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "department",
            "location",
            "asset",
            "reported_by",
            "triaged_by",
            "assigned_to",
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            user_model = get_user_model()
            kwargs["queryset"] = user_model.objects.filter(role__in=["ADMIN", "HELP_DESK", "TECHNICIAN"])
        if db_field.name == "triaged_by":
            user_model = get_user_model()
            kwargs["queryset"] = user_model.objects.filter(role__in=["ADMIN", "HELP_DESK"])
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
