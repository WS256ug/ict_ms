from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Department
from assets.models import Asset, AssetAssignment, AssetCategory, AssetType
from tickets.models import FaultTicket

from .models import SMSNotificationLog


@override_settings(
    EASY_SEND_SMS_ENABLED=True,
    EASY_SEND_SMS_API_KEY="test-api-key",
    EASY_SEND_SMS_SENDER_ID="ICTMS",
    EASY_SEND_SMS_DEFAULT_COUNTRY_CODE="254",
)
class SMSNotificationTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_user(
            email="sms-admin@example.com",
            password="password123",
            first_name="System",
            last_name="Admin",
            role="ADMIN",
            phone_number="+254700000001",
            department=self.department,
        )
        self.technician = self.user_model.objects.create_user(
            email="sms-tech@example.com",
            password="password123",
            first_name="Field",
            last_name="Technician",
            role="TECHNICIAN",
            phone_number="0700000002",
            department=self.department,
        )
        self.requester = self.user_model.objects.create_user(
            email="sms-user@example.com",
            password="password123",
            first_name="Regular",
            last_name="User",
            role="DEPARTMENT_USER",
            phone_number="0700000003",
            department=self.department,
        )
        self.category = AssetCategory.objects.get(name="Computers")
        self.asset_type = AssetType.objects.create(category=self.category, name="SMS Test Laptop")
        self.asset = Asset.objects.create(
            asset_tag="ASSET-SMS-001",
            name="SMS Test Asset",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
            purchase_cost=Decimal("1200.00"),
        )

    @patch(
        "notifications.sms._send_sms_request",
        return_value={"status": True, "scheduled": False, "messageIds": ["ticket-created-123"]},
    )
    def test_creating_fault_ticket_sends_sms_to_admin(self, mocked_sms_request):
        FaultTicket.objects.create(
            title="Printer paper jam",
            description="The front office printer is jammed.",
            ticket_category=FaultTicket.CATEGORY_HARDWARE,
            department=self.department,
            reported_by=self.requester,
            priority=FaultTicket.PRIORITY_HIGH,
        )

        mocked_sms_request.assert_called_once()
        sms_log = SMSNotificationLog.objects.get(event_type=SMSNotificationLog.EVENT_TICKET_CREATED)
        self.assertEqual(sms_log.recipient, self.admin)
        self.assertEqual(sms_log.phone_number, "254700000001")
        self.assertEqual(sms_log.status, SMSNotificationLog.STATUS_SENT)
        self.assertEqual(sms_log.provider_message_id, "ticket-created-123")
        self.assertIn("New fault ticket", sms_log.message)

    @patch(
        "notifications.sms._send_sms_request",
        return_value={"status": True, "scheduled": False, "messageIds": ["ticket-assigned-456"]},
    )
    def test_assigning_ticket_sends_sms_to_technician(self, mocked_sms_request):
        ticket = FaultTicket.objects.create(
            title="Router down",
            description="The branch router is unreachable.",
            ticket_category=FaultTicket.CATEGORY_NETWORK,
            department=self.department,
            reported_by=self.requester,
            priority=FaultTicket.PRIORITY_CRITICAL,
        )

        mocked_sms_request.reset_mock()

        ticket.assigned_to = self.technician
        ticket.status = FaultTicket.STATUS_ASSIGNED
        ticket.save()

        mocked_sms_request.assert_called_once()
        sms_log = SMSNotificationLog.objects.get(event_type=SMSNotificationLog.EVENT_TICKET_ASSIGNED)
        self.assertEqual(sms_log.recipient, self.technician)
        self.assertEqual(sms_log.phone_number, "254700000002")
        self.assertEqual(sms_log.status, SMSNotificationLog.STATUS_SENT)
        self.assertEqual(sms_log.provider_message_id, "ticket-assigned-456")
        self.assertIn(ticket.ticket_id, sms_log.message)

    @patch(
        "notifications.sms._send_sms_request",
        return_value={"status": True, "scheduled": False, "messageIds": ["assignment-overdue-789"]},
    )
    def test_overdue_assignment_command_sends_one_sms_per_day(self, mocked_sms_request):
        assignment = AssetAssignment.objects.create(
            asset=self.asset,
            user=self.requester,
            assignee_identifier="EMP-500",
            assignee_name="Regular User",
            assignee_contact="0700000003",
            assigned_date=timezone.localdate() - timedelta(days=5),
            expected_return=timezone.localdate() - timedelta(days=1),
            issued_by=self.admin,
            purpose="Field support",
        )

        call_command("send_overdue_sms_notifications")
        call_command("send_overdue_sms_notifications")

        mocked_sms_request.assert_called_once()
        sms_log = SMSNotificationLog.objects.get(event_type=SMSNotificationLog.EVENT_ASSIGNMENT_OVERDUE)
        self.assertEqual(sms_log.recipient, self.requester)
        self.assertEqual(sms_log.phone_number, "254700000003")
        self.assertEqual(sms_log.status, SMSNotificationLog.STATUS_SENT)
        self.assertEqual(sms_log.provider_message_id, "assignment-overdue-789")
        self.assertEqual(sms_log.object_id, assignment.pk)
