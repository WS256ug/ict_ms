import csv
import io
import textwrap
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Department
from assets.models import (
    Asset,
    AssetAssignment,
    AssetAudit,
    AssetAuditItem,
    AssetDepreciation,
    AssetLocationHistory,
    InstalledSoftware,
    MaintenanceRecord,
    Software,
)
from tickets.models import FaultTicket
from tickets.permissions import ticket_queryset_for_user


def _asset_inventory_queryset():
    latest_location = AssetLocationHistory.objects.filter(asset=OuterRef("pk")).order_by("-moved_at")
    return (
        Asset.objects.select_related("category", "asset_type", "department")
        .annotate(
            current_location_name=Subquery(latest_location.values("location__name")[:1]),
            current_location_building=Subquery(latest_location.values("location__building")[:1]),
            current_location_room=Subquery(latest_location.values("location__room")[:1]),
        )
        .order_by("asset_tag")
    )


def _location_label(name, building="", room=""):
    if not name:
        return "No location history"

    parts = [name]
    if building:
        parts.append(building)
    if room:
        parts.append(f"Room {room}")
    return " - ".join(parts)


def _sum_decimal(values):
    total = Decimal("0.00")
    for value in values:
        total += value or Decimal("0.00")
    return total


def _display_value(value):
    if value in (None, ""):
        return "-"
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).replace("\r", " ").replace("\n", " ")


def _format_duration(value):
    if not value:
        return "-"

    total_seconds = int(value.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _build_export_urls(request):
    params = request.GET.copy()
    params.pop("export", None)
    export_urls = {}

    for export_type in ("csv", "pdf"):
        export_params = params.copy()
        export_params["export"] = export_type
        export_urls[export_type] = f"{request.path}?{export_params.urlencode()}"

    return export_urls


def _csv_response(filename, columns, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_display_value(value) for value in row])
    return response


def _pdf_escape(value):
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf_bytes(title, columns, rows):
    now = timezone.localtime().strftime("%Y-%m-%d %H:%M")
    lines = [
        title,
        f"Generated on: {now}",
        "",
    ]
    header = " | ".join(columns)
    separator = "-" * min(max(len(header), 40), 120)
    lines.extend(textwrap.wrap(header, width=120) or [""])
    lines.append(separator)

    for row in rows:
        line = " | ".join(_display_value(value) for value in row)
        wrapped_lines = textwrap.wrap(
            line,
            width=120,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
        )
        lines.extend(wrapped_lines or [""])

    if not lines:
        lines = ["No data available."]

    page_groups = [lines[index:index + 46] for index in range(0, len(lines), 46)] or [["No data available."]]

    objects = [None]

    def reserve_object():
        objects.append(b"")
        return len(objects) - 1

    def set_object(object_id, content):
        if isinstance(content, bytes):
            objects[object_id] = content
            return
        objects[object_id] = content.encode("latin-1", "replace")

    font_id = reserve_object()
    set_object(font_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    content_ids = []
    page_ids = []
    for page_lines in page_groups:
        content_id = reserve_object()
        page_id = reserve_object()
        content_ids.append(content_id)
        page_ids.append(page_id)

        operations = ["BT", "/F1 8 Tf", "10 TL", "36 576 Td"]
        for line in page_lines:
            safe_line = _pdf_escape(
                _display_value(line).encode("latin-1", "replace").decode("latin-1")
            )
            operations.append(f"({safe_line}) Tj T*")
        operations.append("ET")
        stream = "\n".join(operations).encode("latin-1", "replace")
        set_object(
            content_id,
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream",
        )

    pages_id = reserve_object()
    catalog_id = reserve_object()

    for page_id, content_id in zip(page_ids, content_ids):
        set_object(
            page_id,
            (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 792 612] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ),
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    set_object(pages_id, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    set_object(catalog_id, f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    output = io.BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, len(objects)):
        offsets.append(output.tell())
        output.write(f"{object_id} 0 obj\n".encode("ascii"))
        output.write(objects[object_id])
        output.write(b"\nendobj\n")

    xref_start = output.tell()
    output.write(f"xref\n0 {len(objects)}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        (
            f"trailer\n<< /Size {len(objects)} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("ascii")
    )
    return output.getvalue()


def _pdf_response(title, filename, columns, rows):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    response.write(_build_pdf_bytes(title, columns, rows))
    return response


def _report_filename(name):
    return f"{slugify(name)}-{timezone.localdate().isoformat()}"


def _render_report(request, template_name, context, title, filename, columns, rows):
    export = request.GET.get("export")
    if export == "csv":
        return _csv_response(filename, columns, rows)
    if export == "pdf":
        return _pdf_response(title, filename, columns, rows)

    context["export_urls"] = _build_export_urls(request)
    return render(request, template_name, context)


# Begin reports_index view
@login_required
def reports_index(request):
    visible_tickets = ticket_queryset_for_user(request.user, FaultTicket.objects.all())
    overdue_tickets = visible_tickets.filter(
        status__in=FaultTicket.OPEN_STATUSES,
        due_date__lt=timezone.now(),
    ).count()
    context = {
        "report_cards": [
            {
                "title": "Ticket Report",
                "description": "Help desk workload, SLA risk, technician performance, and faulty asset trends.",
                "url_name": "reports:ticket_report",
            },
            {
                "title": "Asset Inventory",
                "description": "Complete asset register with category, department, location, and status.",
                "url_name": "reports:asset_inventory",
            },
            {
                "title": "Assets by Department",
                "description": "Department ownership summary with status counts for each team.",
                "url_name": "reports:assets_by_department",
            },
            {
                "title": "Assets by Location",
                "description": "Current asset distribution by latest recorded location.",
                "url_name": "reports:assets_by_location",
            },
            {
                "title": "Assigned Assets",
                "description": "Active assignment register with assignee and return details.",
                "url_name": "reports:assigned_assets",
            },
            {
                "title": "Maintenance Report",
                "description": "Repair, upgrade, and inspection activity with technician status.",
                "url_name": "reports:maintenance_report",
            },
            {
                "title": "Software Inventory",
                "description": "Installed software records and software deployment coverage.",
                "url_name": "reports:software_inventory",
            },
            {
                "title": "Depreciation Report",
                "description": "Asset depreciation values, useful life, and current book value.",
                "url_name": "reports:depreciation_report",
            },
            {
                "title": "Audit Report",
                "description": "Audit runs with found, missing, damaged, and relocated outcomes.",
                "url_name": "reports:audit_report",
            },
        ],
        "stats": {
            "tickets": visible_tickets.count(),
            "overdue_tickets": overdue_tickets,
            "assets": Asset.objects.count(),
            "assigned": AssetAssignment.objects.filter(returned_date__isnull=True).count(),
            "maintenance": MaintenanceRecord.objects.exclude(
                status=MaintenanceRecord.STATUS_COMPLETED
            ).count(),
            "software": InstalledSoftware.objects.count(),
            "depreciation": AssetDepreciation.objects.count(),
            "audits": AssetAudit.objects.count(),
        },
    }
    return render(request, "reports/index.html", context)


# End reports_index view


# Begin ticket_report view
@login_required
def ticket_report(request):
    now = timezone.now()
    today = timezone.localdate()
    resolved_statuses = [FaultTicket.STATUS_RESOLVED, FaultTicket.STATUS_CLOSED]
    ticket_scope = ticket_queryset_for_user(request.user, FaultTicket.objects.all())

    tickets = list(
        ticket_scope.select_related(
            "department",
            "asset",
            "location",
            "reported_by",
            "triaged_by",
            "assigned_to",
        ).order_by("-created_at", "-id")
    )

    open_tickets = [ticket for ticket in tickets if ticket.status in FaultTicket.OPEN_STATUSES]
    overdue_tickets = [
        ticket for ticket in open_tickets if ticket.due_date and ticket.due_date < now
    ]
    resolved_tickets = [ticket for ticket in tickets if ticket.resolution_time]
    responded_tickets = [ticket for ticket in tickets if ticket.response_time]

    average_resolution_time = None
    if resolved_tickets:
        average_resolution_time = sum(
            (ticket.resolution_time for ticket in resolved_tickets),
            timedelta(),
        ) / len(resolved_tickets)

    average_response_time = None
    if responded_tickets:
        average_response_time = sum(
            (ticket.response_time for ticket in responded_tickets),
            timedelta(),
        ) / len(responded_tickets)

    category_labels = dict(FaultTicket.CATEGORY_CHOICES)
    category_data = (
        ticket_scope.values("ticket_category")
        .annotate(
            total=Count("id"),
            open_total=Count("id", filter=Q(status__in=FaultTicket.OPEN_STATUSES)),
            overdue_total=Count(
                "id",
                filter=Q(status__in=FaultTicket.OPEN_STATUSES, due_date__lt=now),
            ),
            resolved_total=Count("id", filter=Q(status__in=resolved_statuses)),
        )
        .order_by("-total", "ticket_category")
    )
    category_rows = [
        {
            "label": category_labels.get(row["ticket_category"], row["ticket_category"]),
            "total": row["total"],
            "open_total": row["open_total"],
            "overdue_total": row["overdue_total"],
            "resolved_total": row["resolved_total"],
        }
        for row in category_data
    ]

    technician_rows = []
    technician_data = (
        ticket_scope.filter(assigned_to__isnull=False)
        .values(
            "assigned_to__first_name",
            "assigned_to__last_name",
            "assigned_to__email",
        )
        .annotate(
            total=Count("id"),
            open_total=Count("id", filter=Q(status__in=FaultTicket.OPEN_STATUSES)),
            overdue_total=Count(
                "id",
                filter=Q(status__in=FaultTicket.OPEN_STATUSES, due_date__lt=now),
            ),
            resolved_total=Count("id", filter=Q(status__in=resolved_statuses)),
        )
        .order_by("-open_total", "-total", "assigned_to__email")
    )
    for row in technician_data:
        full_name = " ".join(
            part
            for part in [row["assigned_to__first_name"], row["assigned_to__last_name"]]
            if part
        ).strip()
        technician_rows.append(
            {
                "label": full_name or row["assigned_to__email"],
                "email": row["assigned_to__email"],
                "total": row["total"],
                "open_total": row["open_total"],
                "overdue_total": row["overdue_total"],
                "resolved_total": row["resolved_total"],
            }
        )

    department_rows = list(
        Department.objects.annotate(
            total=Count("tickets", filter=Q(tickets__in=ticket_scope), distinct=True),
            open_total=Count(
                "tickets",
                filter=Q(
                    tickets__in=ticket_scope,
                    tickets__status__in=FaultTicket.OPEN_STATUSES,
                ),
                distinct=True,
            ),
            overdue_total=Count(
                "tickets",
                filter=Q(
                    tickets__in=ticket_scope,
                    tickets__status__in=FaultTicket.OPEN_STATUSES,
                    tickets__due_date__lt=now,
                ),
                distinct=True,
            ),
            resolved_total=Count(
                "tickets",
                filter=Q(
                    tickets__in=ticket_scope,
                    tickets__status__in=resolved_statuses,
                ),
                distinct=True,
            ),
        )
        .filter(total__gt=0)
        .order_by("-open_total", "-total", "name")
    )

    faulty_asset_rows = list(
        Asset.objects.filter(tickets__in=ticket_scope, tickets__is_asset_fault=True)
        .select_related("department")
        .annotate(
            ticket_total=Count(
                "tickets",
                filter=Q(tickets__in=ticket_scope, tickets__is_asset_fault=True),
                distinct=True,
            ),
            open_total=Count(
                "tickets",
                filter=Q(
                    tickets__in=ticket_scope,
                    tickets__is_asset_fault=True,
                    tickets__status__in=FaultTicket.OPEN_STATUSES,
                ),
                distinct=True,
            ),
            last_ticket_at=Max("tickets__created_at"),
        )
        .order_by("-ticket_total", "-open_total", "asset_tag")[:10]
    )

    queue_rows = [
        {
            "label": "New Tickets",
            "count": ticket_scope.filter(status=FaultTicket.STATUS_OPEN).count(),
            "note": "Fresh tickets waiting for help desk triage.",
        },
        {
            "label": "Unassigned Tickets",
            "count": ticket_scope.filter(
                status__in=[FaultTicket.STATUS_OPEN, FaultTicket.STATUS_TRIAGED],
                assigned_to__isnull=True,
            ).count(),
            "note": "Tickets that still need an owner.",
        },
        {
            "label": "Critical Tickets",
            "count": ticket_scope.filter(
                status__in=FaultTicket.OPEN_STATUSES,
                priority=FaultTicket.PRIORITY_CRITICAL,
            ).count(),
            "note": "Highest urgency work still in the live queue.",
        },
        {
            "label": "Resolved Today",
            "count": ticket_scope.filter(resolved_at__date=today).count(),
            "note": "Tickets resolved during the current day.",
        },
    ]

    context = {
        "tickets": tickets,
        "queue_rows": queue_rows,
        "category_rows": category_rows,
        "technician_rows": technician_rows,
        "department_rows": department_rows,
        "faulty_asset_rows": faulty_asset_rows,
        "stats": {
            "total": len(tickets),
            "open": len(open_tickets),
            "overdue": len(overdue_tickets),
            "critical": sum(
                1
                for ticket in open_tickets
                if ticket.priority == FaultTicket.PRIORITY_CRITICAL
            ),
            "unassigned": sum(1 for ticket in open_tickets if not ticket.assigned_to_id),
            "resolved_today": sum(
                1 for ticket in tickets if ticket.resolved_at and ticket.resolved_at.date() == today
            ),
            "avg_resolution": _format_duration(average_resolution_time),
            "avg_response": _format_duration(average_response_time),
        },
    }
    export_rows = [
        [
            ticket.ticket_id,
            ticket.title,
            ticket.get_ticket_category_display(),
            ticket.get_priority_display(),
            ticket.get_status_display(),
            ticket.department.name if ticket.department else "",
            ticket.asset.asset_tag if ticket.asset else "",
            (
                ticket.assigned_to.get_full_name() or ticket.assigned_to.email
                if ticket.assigned_to
                else ""
            ),
            (
                ticket.reported_by.get_full_name() or ticket.reported_by.email
                if ticket.reported_by
                else ""
            ),
            ticket.created_at,
            ticket.due_date,
            "Yes" if ticket.is_overdue else "No",
            "Yes" if ticket.requires_maintenance else "No",
            "Yes" if ticket.escalated else "No",
            ticket.resolved_at,
        ]
        for ticket in tickets
    ]
    return _render_report(
        request,
        "reports/ticket_report.html",
        context,
        "Ticket Operations Report",
        _report_filename("ticket-report"),
        [
            "Ticket ID",
            "Title",
            "Category",
            "Priority",
            "Status",
            "Department",
            "Asset",
            "Assigned To",
            "Reported By",
            "Created",
            "Due Date",
            "Overdue",
            "Requires Maintenance",
            "Escalated",
            "Resolved At",
        ],
        export_rows,
    )


# End ticket_report view


# Begin asset_inventory_report view
@login_required
def asset_inventory_report(request):
    assets = list(_asset_inventory_queryset())
    context = {
        "assets": assets,
        "stats": {
            "total": len(assets),
            "available": sum(1 for asset in assets if asset.status == Asset.STATUS_AVAILABLE),
            "assigned": sum(1 for asset in assets if asset.status == Asset.STATUS_ASSIGNED),
            "maintenance": sum(1 for asset in assets if asset.status == Asset.STATUS_MAINTENANCE),
        },
    }
    export_rows = [
        [
            asset.asset_tag,
            asset.name,
            asset.category.name,
            asset.asset_type.name,
            asset.department.name if asset.department else "",
            _location_label(
                asset.current_location_name,
                asset.current_location_building,
                asset.current_location_room,
            ),
            asset.get_status_display(),
        ]
        for asset in assets
    ]
    return _render_report(
        request,
        "reports/asset_inventory.html",
        context,
        "Asset Inventory Report",
        _report_filename("asset-inventory"),
        ["Asset Tag", "Name", "Category", "Type", "Department", "Location", "Status"],
        export_rows,
    )


# End asset_inventory_report view


# Begin assets_by_department_report view
@login_required
def assets_by_department_report(request):
    departments = list(
        Department.objects.annotate(
        asset_total=Count("assets", distinct=True),
        available_total=Count(
            "assets",
            filter=Q(assets__status=Asset.STATUS_AVAILABLE),
            distinct=True,
        ),
        assigned_total=Count(
            "assets",
            filter=Q(assets__status=Asset.STATUS_ASSIGNED),
            distinct=True,
        ),
        maintenance_total=Count(
            "assets",
            filter=Q(assets__status=Asset.STATUS_MAINTENANCE),
            distinct=True,
        ),
    ).order_by("-asset_total", "name")
    )
    context = {
        "departments": departments,
        "stats": {
            "departments": len(departments),
            "assets": Asset.objects.exclude(department__isnull=True).count(),
            "without_department": Asset.objects.filter(department__isnull=True).count(),
        },
    }
    export_rows = [
        [
            department.name,
            department.code,
            department.asset_total,
            department.available_total,
            department.assigned_total,
            department.maintenance_total,
        ]
        for department in departments
    ]
    return _render_report(
        request,
        "reports/assets_by_department.html",
        context,
        "Assets by Department Report",
        _report_filename("assets-by-department"),
        ["Department", "Code", "Total Assets", "Available", "Assigned", "Maintenance"],
        export_rows,
    )


# End assets_by_department_report view


# Begin assets_by_location_report view
@login_required
def assets_by_location_report(request):
    rows_by_location = {}

    for asset in _asset_inventory_queryset():
        label = _location_label(
            asset.current_location_name,
            asset.current_location_building,
            asset.current_location_room,
        )
        if label not in rows_by_location:
            rows_by_location[label] = {
                "label": label,
                "total": 0,
                "available": 0,
                "assigned": 0,
                "maintenance": 0,
            }

        row = rows_by_location[label]
        row["total"] += 1
        if asset.status == Asset.STATUS_AVAILABLE:
            row["available"] += 1
        elif asset.status == Asset.STATUS_ASSIGNED:
            row["assigned"] += 1
        elif asset.status == Asset.STATUS_MAINTENANCE:
            row["maintenance"] += 1

    location_rows = sorted(
        rows_by_location.values(),
        key=lambda row: (row["label"] == "No location history", row["label"]),
    )
    context = {
        "location_rows": location_rows,
        "stats": {
            "locations": len(location_rows),
            "assets": sum(row["total"] for row in location_rows),
            "without_location": rows_by_location.get("No location history", {}).get("total", 0),
        },
    }
    export_rows = [
        [
            row["label"],
            row["total"],
            row["available"],
            row["assigned"],
            row["maintenance"],
        ]
        for row in location_rows
    ]
    return _render_report(
        request,
        "reports/assets_by_location.html",
        context,
        "Assets by Location Report",
        _report_filename("assets-by-location"),
        ["Location", "Total Assets", "Available", "Assigned", "Maintenance"],
        export_rows,
    )


# End assets_by_location_report view


# Begin assigned_assets_report view
@login_required
def assigned_assets_report(request):
    assignments = list(
        AssetAssignment.objects.filter(returned_date__isnull=True).select_related(
            "asset",
            "asset__department",
            "issued_by",
            "user",
        )
    )
    overdue_total = sum(
        1
        for assignment in assignments
        if assignment.expected_return and assignment.expected_return < timezone.localdate()
    )
    context = {
        "assignments": assignments,
        "stats": {
            "active": len(assignments),
            "overdue": overdue_total,
            "without_return_date": sum(
                1 for assignment in assignments if not assignment.expected_return
            ),
        },
    }
    export_rows = [
        [
            assignment.asset.asset_tag,
            assignment.asset.name,
            assignment.assignee_display,
            assignment.assignee_identifier,
            assignment.assignee_contact,
            assignment.asset.department.name if assignment.asset.department else "",
            assignment.assigned_date,
            assignment.expected_return,
            assignment.issued_by,
            assignment.purpose,
        ]
        for assignment in assignments
    ]
    return _render_report(
        request,
        "reports/assigned_assets.html",
        context,
        "Assigned Assets Report",
        _report_filename("assigned-assets"),
        [
            "Asset Tag",
            "Asset Name",
            "Assigned To",
            "Assignee ID",
            "Contact",
            "Department",
            "Assigned Date",
            "Expected Return",
            "Issued By",
            "Purpose",
        ],
        export_rows,
    )


# End assigned_assets_report view


# Begin maintenance_report view
@login_required
def maintenance_report(request):
    records = list(
        MaintenanceRecord.objects.select_related("asset", "asset__department").order_by(
            "-start_date",
            "-id",
        )
    )
    context = {
        "records": records,
        "stats": {
            "total": len(records),
            "open": sum(1 for record in records if record.status == MaintenanceRecord.STATUS_OPEN),
            "in_progress": sum(
                1
                for record in records
                if record.status == MaintenanceRecord.STATUS_IN_PROGRESS
            ),
            "completed": sum(
                1
                for record in records
                if record.status == MaintenanceRecord.STATUS_COMPLETED
            ),
            "cost": _sum_decimal(record.cost for record in records),
        },
    }
    export_rows = [
        [
            record.asset.asset_tag,
            record.asset.name,
            record.asset.department.name if record.asset.department else "",
            record.get_maintenance_type_display(),
            record.get_status_display(),
            record.technician,
            record.start_date,
            record.end_date,
            record.cost,
            record.issue_description,
        ]
        for record in records
    ]
    return _render_report(
        request,
        "reports/maintenance_report.html",
        context,
        "Maintenance Report",
        _report_filename("maintenance-report"),
        [
            "Asset Tag",
            "Asset Name",
            "Department",
            "Type",
            "Status",
            "Technician",
            "Start Date",
            "End Date",
            "Cost",
            "Issue",
        ],
        export_rows,
    )


# End maintenance_report view


# Begin software_inventory_report view
@login_required
def software_inventory_report(request):
    installations = list(
        InstalledSoftware.objects.select_related(
            "asset",
            "asset__department",
            "software",
            "installed_by",
        ).order_by("software__name", "asset__asset_tag")
    )
    software_summary = list(
        Software.objects.annotate(
            asset_total=Count("installations", distinct=True)
        ).order_by("-asset_total", "name", "version")
    )
    context = {
        "installations": installations,
        "software_summary": software_summary,
        "stats": {
            "software_titles": len(software_summary),
            "installations": len(installations),
            "assets_covered": Asset.objects.filter(installed_software__isnull=False)
            .distinct()
            .count(),
        },
    }
    export_rows = [
        [
            "Summary",
            software.name,
            software.version,
            software.vendor,
            software.asset_total,
            "",
            "",
            "",
            "",
            "",
        ]
        for software in software_summary
    ] + [
        [
            "Installation",
            installation.software.name,
            installation.software.version,
            installation.software.vendor,
            "",
            installation.asset.asset_tag,
            installation.asset.name,
            installation.asset.department.name if installation.asset.department else "",
            installation.installed_date,
            installation.installed_by,
        ]
        for installation in installations
    ]
    return _render_report(
        request,
        "reports/software_inventory.html",
        context,
        "Software Inventory Report",
        _report_filename("software-inventory"),
        [
            "Section",
            "Software",
            "Version",
            "Vendor",
            "Assets",
            "Asset Tag",
            "Asset Name",
            "Department",
            "Installed Date",
            "Installed By",
        ],
        export_rows,
    )


# End software_inventory_report view


# Begin depreciation_report view
@login_required
def depreciation_report(request):
    records = list(
        AssetDepreciation.objects.select_related("asset", "asset__department").order_by(
            "asset__asset_tag"
        )
    )
    context = {
        "records": records,
        "stats": {
            "total": len(records),
            "purchase_cost": _sum_decimal(record.purchase_cost for record in records),
            "accumulated": _sum_decimal(
                record.accumulated_depreciation for record in records
            ),
            "current_value": _sum_decimal(record.current_value for record in records),
        },
    }
    export_rows = [
        [
            record.asset.asset_tag,
            record.asset.name,
            record.asset.department.name if record.asset.department else "",
            record.purchase_cost,
            record.salvage_value,
            record.useful_life_years,
            record.annual_depreciation,
            record.accumulated_depreciation,
            record.current_value,
            record.start_date,
        ]
        for record in records
    ]
    return _render_report(
        request,
        "reports/depreciation_report.html",
        context,
        "Depreciation Report",
        _report_filename("depreciation-report"),
        [
            "Asset Tag",
            "Asset Name",
            "Department",
            "Purchase Cost",
            "Salvage Value",
            "Useful Life Years",
            "Annual Depreciation",
            "Accumulated Depreciation",
            "Current Value",
            "Start Date",
        ],
        export_rows,
    )


# End depreciation_report view


# Begin audit_report view
@login_required
def audit_report(request):
    audits = list(
        AssetAudit.objects.select_related("conducted_by").annotate(
            total_items=Count("items", distinct=True),
            found_total=Count(
                "items",
                filter=Q(items__status=AssetAuditItem.STATUS_FOUND),
                distinct=True,
            ),
            missing_total=Count(
                "items",
                filter=Q(items__status=AssetAuditItem.STATUS_MISSING),
                distinct=True,
            ),
            damaged_total=Count(
                "items",
                filter=Q(items__status=AssetAuditItem.STATUS_DAMAGED),
                distinct=True,
            ),
            relocated_total=Count(
                "items",
                filter=Q(items__status=AssetAuditItem.STATUS_RELOCATED),
                distinct=True,
            ),
        ).order_by("-audit_date", "-id")
    )
    issue_items = list(
        AssetAuditItem.objects.select_related("audit", "audit__conducted_by", "asset").exclude(
            status=AssetAuditItem.STATUS_FOUND
        ).order_by("-audit__audit_date", "asset__asset_tag")
    )
    context = {
        "audits": audits,
        "issue_items": issue_items,
        "stats": {
            "audits": len(audits),
            "items": AssetAuditItem.objects.count(),
            "missing": AssetAuditItem.objects.filter(
                status=AssetAuditItem.STATUS_MISSING
            ).count(),
            "damaged": AssetAuditItem.objects.filter(
                status=AssetAuditItem.STATUS_DAMAGED
            ).count(),
        },
    }
    export_rows = [
        [
            "Audit Summary",
            audit.audit_date,
            audit.conducted_by,
            "",
            "",
            "",
            audit.total_items,
            audit.found_total,
            audit.missing_total,
            audit.damaged_total,
            audit.relocated_total,
            audit.notes,
        ]
        for audit in audits
    ] + [
        [
            "Audit Issue",
            item.audit.audit_date,
            item.audit.conducted_by,
            item.asset.asset_tag,
            item.asset.name,
            item.get_status_display(),
            "",
            "",
            "",
            "",
            "",
            item.notes,
        ]
        for item in issue_items
    ]
    return _render_report(
        request,
        "reports/audit_report.html",
        context,
        "Audit Report",
        _report_filename("audit-report"),
        [
            "Section",
            "Audit Date",
            "Conducted By",
            "Asset Tag",
            "Asset Name",
            "Status",
            "Total Items",
            "Found",
            "Missing",
            "Damaged",
            "Relocated",
            "Notes",
        ],
        export_rows,
    )


# End audit_report view
