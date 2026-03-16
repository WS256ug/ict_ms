from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from assets.models import MaintenanceRecord

from .forms import (
    FaultTicketCreateForm,
    TicketAttachmentForm,
    TicketCommentForm,
    TicketFilterForm,
    TicketResolutionForm,
    TicketWorkflowForm,
)
from .models import FaultTicket, TicketResolution
from .permissions import (
    can_comment_on_ticket,
    can_create_tickets,
    can_manage_tickets,
    can_triage_tickets,
    can_upload_ticket_attachment,
    can_workflow_ticket,
    enforce_ticket_create_permission,
    enforce_ticket_manage_permission,
    enforce_ticket_view_permission,
    enforce_ticket_workflow_permission,
    ticket_queryset_for_user,
)


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _base_ticket_queryset():
    return FaultTicket.objects.select_related(
        "department",
        "asset",
        "location",
        "reported_by",
        "triaged_by",
        "assigned_to",
        "resolution",
    )


def _queue_definitions():
    today = timezone.localdate()
    now = timezone.now()
    return [
        (
            "new",
            "New Tickets",
            Q(status=FaultTicket.STATUS_OPEN),
            "Fresh tickets waiting for triage.",
        ),
        (
            "unassigned",
            "Unassigned Tickets",
            Q(status__in=[FaultTicket.STATUS_OPEN, FaultTicket.STATUS_TRIAGED], assigned_to__isnull=True),
            "Tickets that still need ownership.",
        ),
        (
            "mine",
            "My Assigned Tickets",
            None,
            "Tickets assigned to the current operator.",
        ),
        (
            "overdue",
            "Overdue Tickets",
            Q(status__in=FaultTicket.OPEN_STATUSES, due_date__lt=now),
            "Open tickets that have passed their SLA due date.",
        ),
        (
            "critical",
            "Critical Tickets",
            Q(status__in=FaultTicket.OPEN_STATUSES, priority=FaultTicket.PRIORITY_CRITICAL),
            "Highest urgency cases still in progress.",
        ),
        (
            "resolved_today",
            "Resolved Today",
            Q(resolved_at__date=today),
            "Tickets resolved during the current day.",
        ),
    ]


def _apply_queue_filter(queryset, queue_key, user):
    if not queue_key:
        return queryset

    for key, _label, query, _note in _queue_definitions():
        if key != queue_key:
            continue
        if key == "mine":
            return queryset.filter(assigned_to=user)
        if query is not None:
            return queryset.filter(query)
        return queryset

    return queryset


def _build_queue_cards(queryset, user, active_queue):
    cards = []
    for key, label, query, note in _queue_definitions():
        if key == "mine":
            count = queryset.filter(assigned_to=user).count()
        else:
            count = queryset.filter(query).count() if query is not None else queryset.count()
        cards.append(
            {
                "key": key,
                "label": label,
                "count": count,
                "note": note,
                "active": key == active_queue,
            }
        )
    return cards


def _ticket_stats(queryset, user):
    now = timezone.now()
    return {
        "total": queryset.count(),
        "open": queryset.filter(status__in=FaultTicket.OPEN_STATUSES).count(),
        "overdue": queryset.filter(status__in=FaultTicket.OPEN_STATUSES, due_date__lt=now).count(),
        "resolved_today": queryset.filter(resolved_at__date=timezone.localdate()).count(),
        "my_assigned": queryset.filter(assigned_to=user).count(),
    }


def _apply_ticket_filters(queryset, filter_form):
    if not filter_form.is_valid():
        return queryset

    search = filter_form.cleaned_data.get("search")
    if search:
        queryset = queryset.filter(
            Q(ticket_id__icontains=search)
            | Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(asset__asset_tag__icontains=search)
            | Q(asset__name__icontains=search)
            | Q(location__name__icontains=search)
            | Q(location__building__icontains=search)
            | Q(location__room__icontains=search)
            | Q(reported_by__email__icontains=search)
            | Q(reported_by__first_name__icontains=search)
            | Q(reported_by__last_name__icontains=search)
        )

    status = filter_form.cleaned_data.get("status")
    if status:
        queryset = queryset.filter(status=status)

    priority = filter_form.cleaned_data.get("priority")
    if priority:
        queryset = queryset.filter(priority=priority)

    ticket_category = filter_form.cleaned_data.get("ticket_category")
    if ticket_category:
        queryset = queryset.filter(ticket_category=ticket_category)

    department = filter_form.cleaned_data.get("department")
    if department:
        queryset = queryset.filter(department=department)

    assigned_to = filter_form.cleaned_data.get("assigned_to")
    if assigned_to:
        queryset = queryset.filter(assigned_to=assigned_to)

    if filter_form.cleaned_data.get("overdue_only"):
        queryset = queryset.filter(status__in=FaultTicket.OPEN_STATUSES, due_date__lt=timezone.now())

    return queryset


def _render_attachment_panel(request, ticket, form=None, success_message=None, status=200):
    form = form or TicketAttachmentForm()
    context = {
        "ticket": ticket,
        "attachments": ticket.attachments.select_related("uploaded_by"),
        "attachment_form": form,
        "can_upload_attachment": can_upload_ticket_attachment(request.user, ticket),
        "attachment_message": success_message,
    }
    return render(request, "tickets/partials/attachment_panel.html", context, status=status)


def _ticket_resolution(ticket):
    try:
        return ticket.resolution
    except TicketResolution.DoesNotExist:
        return None


def _render_comments_panel(request, ticket, form=None, success_message=None, status=200):
    form = form or TicketCommentForm()
    context = {
        "ticket": ticket,
        "comments": ticket.comments.select_related("user"),
        "comment_form": form,
        "can_comment": can_comment_on_ticket(request.user, ticket),
        "comment_message": success_message,
    }
    return render(request, "tickets/partials/comments_panel.html", context, status=status)


def _render_workflow_panel(request, ticket, form=None, success_message=None, status=200):
    form = form or TicketWorkflowForm(instance=ticket, user=request.user)
    context = {
        "ticket": ticket,
        "workflow_form": form,
        "can_workflow_ticket": can_workflow_ticket(request.user, ticket),
        "can_triage_ticket": can_triage_tickets(request.user),
        "workflow_message": success_message,
    }
    return render(request, "tickets/partials/workflow_panel.html", context, status=status)


def _render_resolution_panel(request, ticket, form=None, success_message=None, status=200):
    resolution_instance = _ticket_resolution(ticket)
    form = form or TicketResolutionForm(instance=resolution_instance)
    context = {
        "ticket": ticket,
        "resolution": resolution_instance,
        "resolution_form": form,
        "can_workflow_ticket": can_workflow_ticket(request.user, ticket),
        "resolution_message": success_message,
    }
    return render(request, "tickets/partials/resolution_panel.html", context, status=status)


@login_required
def ticket_list(request):
    visible_tickets = ticket_queryset_for_user(request.user, _base_ticket_queryset())
    active_queue = request.GET.get("queue", "").strip()
    queue_filtered_tickets = _apply_queue_filter(visible_tickets, active_queue, request.user)
    filter_form = TicketFilterForm(request.GET or None, user=request.user)
    filtered_tickets = _apply_ticket_filters(queue_filtered_tickets, filter_form)

    paginator = Paginator(filtered_tickets.order_by("-created_at"), 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    filter_querystring = request.GET.copy()
    filter_querystring.pop("page", None)

    context = {
        "page_obj": page_obj,
        "filter_form": filter_form,
        "filter_querystring": filter_querystring,
        "stats": _ticket_stats(visible_tickets, request.user),
        "queue_cards": _build_queue_cards(visible_tickets, request.user, active_queue),
        "active_queue": active_queue,
        "can_create_ticket": can_create_tickets(request.user),
        "can_manage_ticket": can_manage_tickets(request.user),
    }

    if _is_htmx(request):
        return render(request, "tickets/partials/ticket_list_content.html", context)

    return render(request, "tickets/ticket_list.html", context)


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)

    context = {
        "ticket": ticket,
        "comments": ticket.comments.select_related("user"),
        "comment_form": TicketCommentForm(),
        "attachment_form": TicketAttachmentForm(),
        "attachments": ticket.attachments.select_related("uploaded_by"),
        "workflow_form": TicketWorkflowForm(instance=ticket, user=request.user),
        "resolution_form": TicketResolutionForm(instance=_ticket_resolution(ticket)),
        "resolution": _ticket_resolution(ticket),
        "can_manage_ticket": can_manage_tickets(request.user),
        "can_workflow_ticket": can_workflow_ticket(request.user, ticket),
        "can_triage_ticket": can_triage_tickets(request.user),
        "can_comment": can_comment_on_ticket(request.user, ticket),
        "can_upload_attachment": can_upload_ticket_attachment(request.user, ticket),
    }

    return render(request, "tickets/ticket_detail.html", context)


@login_required
def ticket_create(request):
    enforce_ticket_create_permission(request.user)

    if request.method == "POST":
        form = FaultTicketCreateForm(request.POST, user=request.user)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.reported_by = request.user
            ticket.save()
            messages.success(request, f"Ticket {ticket.ticket_id} created successfully.")
            return redirect("tickets:ticket_detail", pk=ticket.pk)
    else:
        form = FaultTicketCreateForm(user=request.user)

    return render(
        request,
        "tickets/ticket_form.html",
        {
            "form": form,
            "action": "Create",
            "page_title": "Create Help Desk Ticket",
        },
    )


@login_required
@require_GET
def ticket_asset_field(request):
    form = FaultTicketCreateForm(request.GET or None, user=request.user)
    context = {
        "asset_field": form["asset"],
        "asset_help_text": (
            "Only assets from the selected department are shown."
            if form.fields["asset"].queryset.exists()
            else "Select a department to load its assets."
        ),
    }
    return render(request, "tickets/partials/ticket_asset_field.html", context)


@login_required
def ticket_update(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)

    reporter_can_edit = ticket.reported_by_id == request.user.pk and ticket.status == FaultTicket.STATUS_OPEN
    staff_can_edit = can_workflow_ticket(request.user, ticket) or can_triage_tickets(request.user)
    if not (reporter_can_edit or staff_can_edit):
        enforce_ticket_workflow_permission(request.user, ticket)

    if request.method == "POST":
        form = FaultTicketCreateForm(request.POST, instance=ticket, user=request.user)
        if form.is_valid():
            ticket = form.save()
            messages.success(request, f"Ticket {ticket.ticket_id} updated successfully.")
            return redirect("tickets:ticket_detail", pk=ticket.pk)
    else:
        form = FaultTicketCreateForm(instance=ticket, user=request.user)

    return render(
        request,
        "tickets/ticket_form.html",
        {
            "form": form,
            "ticket": ticket,
            "action": "Update",
            "page_title": f"Update {ticket.ticket_id}",
        },
    )


@login_required
@require_GET
def ticket_workflow_panel(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)
    enforce_ticket_workflow_permission(request.user, ticket)
    return _render_workflow_panel(request, ticket)


@login_required
@require_POST
def ticket_workflow_update(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)
    enforce_ticket_workflow_permission(request.user, ticket)

    form = TicketWorkflowForm(request.POST, instance=ticket, user=request.user)
    if form.is_valid():
        ticket = form.save()
        if ticket.status != FaultTicket.STATUS_OPEN:
            ticket.mark_first_response()
            ticket.save(update_fields=["first_response_at", "updated_at"])

        if _is_htmx(request):
            return _render_workflow_panel(
                request,
                ticket,
                success_message="Workflow updated successfully.",
            )

        messages.success(request, "Workflow updated successfully.")
        return redirect("tickets:ticket_detail", pk=ticket.pk)

    if _is_htmx(request):
        return _render_workflow_panel(request, ticket, form=form, status=400)

    messages.error(request, "Workflow update failed. Check the form and try again.")
    return redirect("tickets:ticket_detail", pk=ticket.pk)


@login_required
@require_GET
def ticket_resolution_panel(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)
    enforce_ticket_workflow_permission(request.user, ticket)
    return _render_resolution_panel(request, ticket)


@login_required
@require_POST
def ticket_resolution_update(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)
    enforce_ticket_workflow_permission(request.user, ticket)

    resolution_instance = _ticket_resolution(ticket)
    form = TicketResolutionForm(request.POST, instance=resolution_instance)
    if form.is_valid():
        resolution = form.save(commit=False)
        resolution.ticket = ticket
        resolution.resolved_by = request.user
        if not resolution.resolved_at:
            resolution.resolved_at = timezone.now()
        resolution.save()

        ticket.status = FaultTicket.STATUS_RESOLVED
        ticket.resolved_at = resolution.resolved_at
        ticket.mark_first_response(when=resolution.resolved_at)
        ticket.save()

        if _is_htmx(request):
            ticket.refresh_from_db()
            return _render_resolution_panel(
                request,
                ticket,
                success_message="Resolution saved and ticket marked resolved.",
            )

        messages.success(request, "Resolution saved and ticket marked resolved.")
        return redirect("tickets:ticket_detail", pk=ticket.pk)

    if _is_htmx(request):
        return _render_resolution_panel(request, ticket, form=form, status=400)

    messages.error(request, "Resolution update failed. Check the form and try again.")
    return redirect("tickets:ticket_detail", pk=ticket.pk)


@login_required
@require_GET
def ticket_comments_panel(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)
    return _render_comments_panel(request, ticket)


@login_required
@require_POST
def ticket_comment_create(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)

    if not can_comment_on_ticket(request.user, ticket):
        enforce_ticket_manage_permission(request.user)

    form = TicketCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.user = request.user
        comment.save()

        if can_workflow_ticket(request.user, ticket):
            ticket.mark_first_response()
            ticket.save(update_fields=["first_response_at", "updated_at"])

        if _is_htmx(request):
            ticket.refresh_from_db()
            return _render_comments_panel(
                request,
                ticket,
                success_message="Comment added successfully.",
            )

        messages.success(request, "Ticket comment added.")
    else:
        if _is_htmx(request):
            return _render_comments_panel(request, ticket, form=form, status=400)
        messages.error(request, "Please enter a comment before submitting.")

    return redirect(f"{reverse('tickets:ticket_detail', args=[ticket.pk])}#ticket-comments")


@login_required
@require_GET
def ticket_attachment_panel(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)
    return _render_attachment_panel(request, ticket)


@login_required
@require_POST
def ticket_attachment_upload(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)

    if not can_upload_ticket_attachment(request.user, ticket):
        enforce_ticket_manage_permission(request.user)

    form = TicketAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        attachment = form.save(commit=False)
        attachment.ticket = ticket
        attachment.uploaded_by = request.user
        attachment.save()

        if _is_htmx(request):
            ticket.refresh_from_db()
            return _render_attachment_panel(
                request,
                ticket,
                success_message="Attachment uploaded successfully.",
            )

        messages.success(request, "Attachment uploaded successfully.")
        return redirect("tickets:ticket_detail", pk=ticket.pk)

    if _is_htmx(request):
        return _render_attachment_panel(request, ticket, form=form, status=400)

    messages.error(request, "Attachment upload failed. Check the form and try again.")
    return redirect("tickets:ticket_detail", pk=ticket.pk)


@login_required
@require_POST
def ticket_create_maintenance(request, pk):
    ticket = get_object_or_404(_base_ticket_queryset(), pk=pk)
    enforce_ticket_view_permission(request.user, ticket)
    enforce_ticket_workflow_permission(request.user, ticket)

    if not ticket.can_create_maintenance:
        messages.error(
            request,
            "This ticket must be asset-linked and marked as an asset fault or maintenance issue.",
        )
        return redirect("tickets:ticket_detail", pk=ticket.pk)

    technician_name = request.user.get_full_name() or request.user.email
    record = MaintenanceRecord.objects.create(
        asset=ticket.asset,
        issue_description=f"{ticket.ticket_id}: {ticket.title}\n\n{ticket.description}",
        maintenance_type=MaintenanceRecord.TYPE_REPAIR,
        start_date=timezone.localdate(),
        technician=technician_name,
        status=MaintenanceRecord.STATUS_OPEN,
        notes=f"Created from ticket {ticket.ticket_id}.",
    )

    ticket.comments.create(
        user=request.user,
        comment=f"Maintenance record #{record.pk} was created for {ticket.asset.asset_tag}.",
    )
    ticket.requires_maintenance = True
    if ticket.status in {FaultTicket.STATUS_OPEN, FaultTicket.STATUS_TRIAGED}:
        ticket.status = FaultTicket.STATUS_IN_PROGRESS
    if not ticket.assigned_to_id:
        ticket.assigned_to = request.user
    ticket.mark_first_response()
    ticket.save()

    messages.success(
        request,
        f"Maintenance record for {ticket.asset.asset_tag} created from {ticket.ticket_id}.",
    )
    return redirect("assets:maintenance_detail", pk=record.pk)
