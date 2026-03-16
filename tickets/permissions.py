from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import FaultTicket


def is_ticket_supervisor(user):
    return (
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_admin", False)
            or getattr(user, "is_help_desk", False)
            or getattr(user, "is_management", False)
        )
    )


def can_view_all_tickets(user):
    return is_ticket_supervisor(user)


def can_create_tickets(user):
    return getattr(user, "is_authenticated", False) and not getattr(user, "is_management", False)


def can_triage_tickets(user):
    return (
        getattr(user, "is_authenticated", False)
        and (getattr(user, "is_admin", False) or getattr(user, "is_help_desk", False))
    )


def can_manage_tickets(user):
    return (
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_admin", False)
            or getattr(user, "is_help_desk", False)
            or getattr(user, "is_technician", False)
        )
    )


def can_workflow_ticket(user, ticket):
    if not can_manage_tickets(user):
        return False
    if getattr(user, "is_admin", False) or getattr(user, "is_help_desk", False):
        return True
    return ticket.assigned_to_id == user.pk


def can_comment_on_ticket(user, ticket):
    if not getattr(user, "is_authenticated", False):
        return False
    if can_workflow_ticket(user, ticket):
        return True
    return ticket.reported_by_id == user.pk


def can_upload_ticket_attachment(user, ticket):
    return can_comment_on_ticket(user, ticket)


def ticket_queryset_for_user(user, queryset=None):
    queryset = queryset if queryset is not None else FaultTicket.objects.all()

    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    if can_view_all_tickets(user):
        return queryset

    if getattr(user, "is_technician", False):
        return queryset.filter(Q(assigned_to=user) | Q(reported_by=user))

    return queryset.filter(reported_by=user)


def enforce_ticket_view_permission(user, ticket):
    if can_view_all_tickets(user):
        return
    if getattr(user, "is_technician", False) and ticket.assigned_to_id == getattr(user, "pk", None):
        return
    if ticket.reported_by_id == getattr(user, "pk", None):
        return
    raise PermissionDenied


def enforce_ticket_manage_permission(user):
    if can_manage_tickets(user):
        return
    raise PermissionDenied


def enforce_ticket_workflow_permission(user, ticket):
    if can_workflow_ticket(user, ticket):
        return
    raise PermissionDenied


def enforce_ticket_create_permission(user):
    if can_create_tickets(user):
        return
    raise PermissionDenied
