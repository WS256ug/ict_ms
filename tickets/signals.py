from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from notifications.models import SMSNotificationLog
from notifications.sms import send_sms_to_user

from .models import FaultTicket


def _ticket_summary(ticket):
    summary = f"{ticket.ticket_id}: {ticket.title}"
    return summary[:120]


@receiver(pre_save, sender=FaultTicket)
def stash_previous_ticket_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_assigned_to_id = None
        return

    previous_state = sender.objects.filter(pk=instance.pk).values("assigned_to_id").first() or {}
    instance._previous_assigned_to_id = previous_state.get("assigned_to_id")


@receiver(post_save, sender=FaultTicket)
def send_ticket_sms_notifications(sender, instance, created, **kwargs):
    if created:
        User = get_user_model()
        admins = User.objects.filter(role="ADMIN", is_active=True).exclude(phone_number__isnull=True).exclude(
            phone_number__exact=""
        )
        reporter_name = instance.reported_by.get_full_name().strip() or instance.reported_by.email
        message = (
            f"New fault ticket {_ticket_summary(instance)} reported by {reporter_name}. "
            f"Priority: {instance.get_priority_display()}."
        )
        for admin in admins:
            send_sms_to_user(
                admin,
                message,
                event_type=SMSNotificationLog.EVENT_TICKET_CREATED,
                related_object=instance,
            )
        return

    previous_assigned_to_id = getattr(instance, "_previous_assigned_to_id", None)
    if not instance.assigned_to_id or instance.assigned_to_id == previous_assigned_to_id:
        return

    assignee_name = instance.assigned_to.get_full_name().strip() or instance.assigned_to.email
    message = (
        f"Hello {assignee_name}, ticket {_ticket_summary(instance)} has been assigned to you. "
        f"Status: {instance.get_status_display()}."
    )
    send_sms_to_user(
        instance.assigned_to,
        message,
        event_type=SMSNotificationLog.EVENT_TICKET_ASSIGNED,
        related_object=instance,
    )
