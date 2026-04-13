from django.core.management.base import BaseCommand
from django.utils import timezone

from assets.models import AssetAssignment
from notifications.models import SMSNotificationLog
from notifications.sms import send_sms_to_number, sms_already_sent


class Command(BaseCommand):
    help = "Send SMS reminders for overdue asset assignments."

    def handle(self, *args, **options):
        today = timezone.localdate()
        overdue_assignments = AssetAssignment.objects.select_related("asset", "user").filter(
            returned_date__isnull=True,
            expected_return__lt=today,
        )

        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for assignment in overdue_assignments:
            phone_candidates = [
                getattr(getattr(assignment, "user", None), "phone_number", ""),
                assignment.assignee_contact,
            ]
            phone_number = next((value for value in phone_candidates if value), "")

            if sms_already_sent(
                SMSNotificationLog.EVENT_ASSIGNMENT_OVERDUE,
                assignment,
                phone_number,
            ):
                skipped_count += 1
                continue

            overdue_days = max((today - assignment.expected_return).days, 0)
            assignee_name = assignment.assignee_name or (
                assignment.user.get_full_name().strip() if assignment.user_id else "User"
            )
            message = (
                f"Hello {assignee_name}, asset {assignment.asset.asset_tag} ({assignment.asset.name}) "
                f"is overdue by {overdue_days} day(s). Please return it as soon as possible."
            )
            result = send_sms_to_number(
                phone_number,
                message,
                event_type=SMSNotificationLog.EVENT_ASSIGNMENT_OVERDUE,
                recipient=assignment.user,
                related_object=assignment,
            )

            if result.ok:
                sent_count += 1
            elif result.status == SMSNotificationLog.STATUS_SKIPPED:
                skipped_count += 1
            else:
                failed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Overdue assignment SMS run complete. Sent: {sent_count}, "
                f"Skipped: {skipped_count}, Failed: {failed_count}."
            )
        )
