from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import render
from django.utils import timezone

from accounts.models import Department, User
from assets.models import (
    Asset,
    AssetAssignment,
    AssetAudit,
    AssetAuditItem,
    InstalledSoftware,
    Location,
    Software,
)
from maintenance.models import MaintenanceLog, MaintenanceSchedule
from tickets.models import FaultTicket


def _safe_count(source):
    try:
        if hasattr(source, "objects"):
            return source.objects.count()
        return source.count()
    except (OperationalError, ProgrammingError):
        return 0


def _safe_list(queryset, limit=None):
    try:
        if limit is not None:
            queryset = queryset[:limit]
        return list(queryset)
    except (OperationalError, ProgrammingError):
        return []


def _percentage(value, total):
    if not total:
        return 0
    return round((value / total) * 100)


@login_required
def landing_page(request):
    today = timezone.localdate()
    now = timezone.now()
    warranty_window = today + timedelta(days=30)

    asset_total = _safe_count(Asset)
    department_total = _safe_count(Department)
    user_total = _safe_count(User)
    software_total = _safe_count(Software)
    software_installation_total = _safe_count(InstalledSoftware)
    location_total = _safe_count(Location)
    maintenance_log_total = _safe_count(MaintenanceLog)
    audit_total = _safe_count(AssetAudit)
    active_assignment_total = _safe_count(
        AssetAssignment.objects.filter(returned_date__isnull=True)
    )
    overdue_assignment_total = _safe_count(
        AssetAssignment.objects.filter(
            returned_date__isnull=True,
            expected_return__lt=today,
        )
    )
    in_progress_maintenance_total = _safe_count(
        MaintenanceLog.objects.filter(status="IN_PROGRESS")
    )
    warranty_due_total = _safe_count(
        Asset.objects.filter(
            warranty_expiry__isnull=False,
            warranty_expiry__gte=today,
            warranty_expiry__lte=warranty_window,
        )
    )

    open_ticket_queryset = FaultTicket.objects.filter(status__in=FaultTicket.OPEN_STATUSES)
    open_ticket_total = _safe_count(open_ticket_queryset)
    pending_schedule_total = _safe_count(MaintenanceSchedule.objects.filter(is_completed=False))
    due_service_total = _safe_count(
        MaintenanceSchedule.objects.filter(
            is_completed=False,
            scheduled_date__lte=today,
        )
    )
    overdue_ticket_total = _safe_count(
        open_ticket_queryset.filter(
            due_date__lt=now,
        )
    )

    asset_status_counts = {
        row["status"]: row["total"]
        for row in _safe_list(Asset.objects.values("status").annotate(total=Count("id")))
    }
    available_asset_total = asset_status_counts.get(Asset.STATUS_AVAILABLE, 0)
    assigned_asset_total = asset_status_counts.get(Asset.STATUS_ASSIGNED, 0)
    maintenance_asset_total = asset_status_counts.get(Asset.STATUS_MAINTENANCE, 0)
    reserved_asset_total = asset_status_counts.get(Asset.STATUS_RESERVED, 0)
    retired_asset_total = asset_status_counts.get(Asset.STATUS_RETIRED, 0)
    lost_asset_total = asset_status_counts.get(Asset.STATUS_LOST, 0)

    open_priority_counts = {
        row["priority"]: row["total"]
        for row in _safe_list(
            open_ticket_queryset.values("priority").annotate(total=Count("id"))
        )
    }

    department_cards = _safe_list(
        Department.objects.annotate(
            asset_total=Count("assets", distinct=True),
            ticket_total=Count("tickets", distinct=True),
            user_total=Count("users", distinct=True),
        ).order_by("-asset_total", "name"),
        5,
    )
    recent_tickets = _safe_list(
        FaultTicket.objects.select_related("department", "assigned_to", "reported_by", "asset").order_by(
            "-created_at"
        ),
        6,
    )
    maintenance_queue = _safe_list(
        MaintenanceSchedule.objects.select_related("asset", "assigned_to")
        .filter(is_completed=False)
        .order_by("scheduled_date"),
        5,
    )
    recent_maintenance = _safe_list(
        MaintenanceLog.objects.select_related("asset", "performed_by").order_by("-performed_at"),
        5,
    )
    recent_assignments = _safe_list(
        AssetAssignment.objects.select_related("asset", "issued_by")
        .filter(returned_date__isnull=True)
        .order_by("-assigned_date", "-id"),
        6,
    )
    warranty_alerts = _safe_list(
        Asset.objects.select_related("department")
        .filter(
            warranty_expiry__isnull=False,
            warranty_expiry__gte=today,
            warranty_expiry__lte=warranty_window,
        )
        .order_by("warranty_expiry", "asset_tag"),
        6,
    )
    latest_audit_list = _safe_list(
        AssetAudit.objects.select_related("conducted_by").order_by("-audit_date", "-id"),
        1,
    )

    for ticket in recent_tickets:
        ticket.age_hours = int((now - ticket.created_at).total_seconds() // 3600)

    for schedule in maintenance_queue:
        schedule.days_until = (
            (schedule.scheduled_date - today).days if schedule.scheduled_date else None
        )

    for assignment in recent_assignments:
        assignment.days_to_return = (
            (assignment.expected_return - today).days
            if assignment.expected_return
            else None
        )
        if assignment.days_to_return is None:
            assignment.return_badge = "Open-ended"
            assignment.return_badge_tone = "secondary"
        elif assignment.days_to_return < 0:
            assignment.return_badge = f"{abs(assignment.days_to_return)} day(s) overdue"
            assignment.return_badge_tone = "danger"
        elif assignment.days_to_return == 0:
            assignment.return_badge = "Due today"
            assignment.return_badge_tone = "warning"
        else:
            assignment.return_badge = f"In {assignment.days_to_return} day(s)"
            assignment.return_badge_tone = "info"

    for asset in warranty_alerts:
        asset.warranty_days_left = (asset.warranty_expiry - today).days

    latest_audit_snapshot = None
    if latest_audit_list:
        latest_audit = latest_audit_list[0]
        latest_audit_counts = {
            row["status"]: row["total"]
            for row in _safe_list(
                AssetAuditItem.objects.filter(audit=latest_audit)
                .values("status")
                .annotate(total=Count("id"))
            )
        }
        latest_audit_snapshot = {
            "audit": latest_audit,
            "found": latest_audit_counts.get(AssetAuditItem.STATUS_FOUND, 0),
            "missing": latest_audit_counts.get(AssetAuditItem.STATUS_MISSING, 0),
            "damaged": latest_audit_counts.get(AssetAuditItem.STATUS_DAMAGED, 0),
            "relocated": latest_audit_counts.get(AssetAuditItem.STATUS_RELOCATED, 0),
            "total_items": sum(latest_audit_counts.values()),
        }

    if request.user.is_authenticated:
        user_name = request.user.get_full_name() or request.user.email
        user_role = (
            request.user.get_role_display()
            if hasattr(request.user, "get_role_display")
            else "Authenticated User"
        )
    else:
        user_name = "Operations Desk"
        user_role = "Guest Preview"

    context = {
        "page_date": today,
        "page_year": today.year,
        "user_name": user_name,
        "user_role": user_role,
        "summary_cards": [
            {
                "label": "Assets Registered",
                "value": asset_total,
                "icon": "ph ph-desktop-tower",
                "tone": "teal",
                "detail": f"{available_asset_total} available and {assigned_asset_total} assigned",
                "footer": f"{maintenance_asset_total} currently in maintenance",
            },
            {
                "label": "Active Assignments",
                "value": active_assignment_total,
                "icon": "ph ph-user-switch",
                "tone": "blue",
                "detail": "Assets currently issued across departments and visitors",
                "footer": f"{overdue_assignment_total} overdue returns",
            },
            {
                "label": "Open Help Desk Tickets",
                "value": open_ticket_total,
                "icon": "ph ph-warning-octagon",
                "tone": "red",
                "detail": "Current incidents still in the service queue",
                "footer": f"{overdue_ticket_total} overdue ticket cases",
            },
            {
                "label": "Maintenance Queue",
                "value": pending_schedule_total,
                "icon": "ph ph-wrench",
                "tone": "amber",
                "detail": "Scheduled jobs waiting for completion",
                "footer": f"{due_service_total} due now and {in_progress_maintenance_total} in progress",
            },
        ],
        "asset_status_rows": [
            {
                "label": "Available",
                "count": available_asset_total,
                "percent": _percentage(available_asset_total, asset_total),
                "tone": "green",
            },
            {
                "label": "Assigned",
                "count": assigned_asset_total,
                "percent": _percentage(assigned_asset_total, asset_total),
                "tone": "blue",
            },
            {
                "label": "Under Maintenance",
                "count": maintenance_asset_total,
                "percent": _percentage(maintenance_asset_total, asset_total),
                "tone": "amber",
            },
            {
                "label": "Retired",
                "count": retired_asset_total,
                "percent": _percentage(retired_asset_total, asset_total),
                "tone": "purple",
            },
            {
                "label": "Reserved / Lost",
                "count": reserved_asset_total + lost_asset_total,
                "percent": _percentage(reserved_asset_total + lost_asset_total, asset_total),
                "tone": "red",
            },
        ],
        "ticket_priority_rows": [
            {
                "label": "Critical",
                "count": open_priority_counts.get("CRITICAL", 0),
                "percent": _percentage(open_priority_counts.get("CRITICAL", 0), open_ticket_total),
                "tone": "red",
            },
            {
                "label": "High",
                "count": open_priority_counts.get("HIGH", 0),
                "percent": _percentage(open_priority_counts.get("HIGH", 0), open_ticket_total),
                "tone": "amber",
            },
            {
                "label": "Medium",
                "count": open_priority_counts.get("MEDIUM", 0),
                "percent": _percentage(open_priority_counts.get("MEDIUM", 0), open_ticket_total),
                "tone": "blue",
            },
            {
                "label": "Low",
                "count": open_priority_counts.get("LOW", 0),
                "percent": _percentage(open_priority_counts.get("LOW", 0), open_ticket_total),
                "tone": "green",
            },
        ],
        "command_metrics": [
            {
                "label": "Service Visibility",
                "value": open_ticket_total + pending_schedule_total + active_assignment_total,
                "suffix": "",
                "note": "Combined live workload across tickets, maintenance, and assignments",
            },
            {
                "label": "Warranty Watch",
                "value": warranty_due_total,
                "suffix": "",
                "note": "Assets with warranty expiring in the next 30 days",
            },
            {
                "label": "Overdue Actions",
                "value": overdue_ticket_total + overdue_assignment_total,
                "suffix": "",
                "note": "Overdue tickets and late asset returns needing follow-up",
            },
        ],
        "operations_snapshot": [
            {
                "label": "Departments",
                "value": department_total,
                "note": "Organizational units covered by the system",
            },
            {
                "label": "Users",
                "value": user_total,
                "note": "Registered users with access roles",
            },
            {
                "label": "Locations",
                "value": location_total,
                "note": "Tracked offices, stores, and rooms",
            },
            {
                "label": "Software Titles",
                "value": software_total,
                "note": "Distinct software records in inventory",
            },
            {
                "label": "Software Installs",
                "value": software_installation_total,
                "note": "Installed software linked to assets",
            },
            {
                "label": "Audit Cycles",
                "value": audit_total,
                "note": "Completed asset audit sessions",
            },
        ],
        "department_cards": department_cards,
        "recent_tickets": recent_tickets,
        "maintenance_queue": maintenance_queue,
        "recent_maintenance": recent_maintenance,
        "recent_assignments": recent_assignments,
        "warranty_alerts": warranty_alerts,
        "latest_audit_snapshot": latest_audit_snapshot,
        "software_total": software_total,
        "maintenance_log_total": maintenance_log_total,
    }
    return render(request, "dashboard.html", context)
