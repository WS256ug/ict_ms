import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department
from assets.models import (
    Asset,
    AssetCategory,
    AssetLocationHistory,
    AssetType,
    Location,
    MaintenanceRecord,
)

from .models import FaultTicket, TicketAttachment, TicketResolution


class TicketViewTests(TestCase):
    def setUp(self):
        self.temp_media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media_root)
        self.media_override.enable()

        self.ict_department = Department.objects.create(name="ICT", code="ICT")
        self.finance_department = Department.objects.create(name="Finance", code="FIN")
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_user(
            email="tickets-admin@example.com",
            password="password123",
            first_name="Ticket",
            last_name="Admin",
            role="ADMIN",
            department=self.ict_department,
        )
        self.help_desk = self.user_model.objects.create_user(
            email="tickets-helpdesk@example.com",
            password="password123",
            first_name="Help",
            last_name="Desk",
            role="HELP_DESK",
            department=self.ict_department,
        )
        self.technician = self.user_model.objects.create_user(
            email="tickets-tech@example.com",
            password="password123",
            first_name="Ticket",
            last_name="Tech",
            role="TECHNICIAN",
            department=self.ict_department,
        )
        self.requester = self.user_model.objects.create_user(
            email="requester@example.com",
            password="password123",
            first_name="Fault",
            last_name="Reporter",
            role="DEPARTMENT_USER",
            department=self.ict_department,
        )
        self.other_requester = self.user_model.objects.create_user(
            email="other-requester@example.com",
            password="password123",
            first_name="Other",
            last_name="Reporter",
            role="DEPARTMENT_USER",
            department=self.finance_department,
        )
        self.management = self.user_model.objects.create_user(
            email="management@example.com",
            password="password123",
            first_name="Management",
            last_name="Viewer",
            role="MANAGEMENT",
            department=self.finance_department,
        )
        self.category = AssetCategory.objects.get(name="Computers")
        self.asset_type = AssetType.objects.create(category=self.category, name="Ticket Laptop")
        self.location = Location.objects.create(name="ICT Office", building="Admin Block", room="12")
        self.finance_location = Location.objects.create(
            name="Finance Office",
            building="Finance Block",
            room="3",
        )
        self.asset = Asset.objects.create(
            asset_tag="ASSET-TKT-001",
            name="Ticket Laptop",
            category=self.category,
            asset_type=self.asset_type,
            department=self.ict_department,
        )
        self.finance_asset = Asset.objects.create(
            asset_tag="ASSET-TKT-002",
            name="Finance Desktop",
            category=self.category,
            asset_type=self.asset_type,
            department=self.finance_department,
        )
        AssetLocationHistory.objects.create(
            asset=self.asset,
            location=self.location,
            moved_by=self.admin,
            moved_at=timezone.now(),
        )
        AssetLocationHistory.objects.create(
            asset=self.finance_asset,
            location=self.finance_location,
            moved_by=self.admin,
            moved_at=timezone.now(),
        )

        self.my_ticket = FaultTicket.objects.create(
            title="Laptop not powering on",
            description="The laptop does not power on after charging.",
            ticket_category=FaultTicket.CATEGORY_HARDWARE,
            is_asset_fault=True,
            asset=self.asset,
            location=self.location,
            department=self.ict_department,
            reported_by=self.requester,
            priority=FaultTicket.PRIORITY_HIGH,
        )
        self.other_ticket = FaultTicket.objects.create(
            title="Printer offline",
            description="Finance printer is offline.",
            ticket_category=FaultTicket.CATEGORY_NETWORK,
            department=self.finance_department,
            reported_by=self.other_requester,
            priority=FaultTicket.PRIORITY_LOW,
        )
        self.overdue_ticket = FaultTicket.objects.create(
            title="Switch outage",
            description="Network switch keeps dropping ports.",
            ticket_category=FaultTicket.CATEGORY_NETWORK,
            department=self.ict_department,
            reported_by=self.requester,
            priority=FaultTicket.PRIORITY_CRITICAL,
            assigned_to=self.technician,
            status=FaultTicket.STATUS_IN_PROGRESS,
            due_date=timezone.now() - timedelta(hours=2),
        )
        self.technician_reported_ticket = FaultTicket.objects.create(
            title="Email sync issue",
            description="Technician raised a mail sync incident.",
            ticket_category=FaultTicket.CATEGORY_SOFTWARE,
            department=self.ict_department,
            reported_by=self.technician,
            status=FaultTicket.STATUS_TRIAGED,
            triaged_by=self.help_desk,
            priority=FaultTicket.PRIORITY_MEDIUM,
        )

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media_root, ignore_errors=True)
        super().tearDown()

    def test_department_user_list_only_shows_their_own_tickets(self):
        self.client.force_login(self.requester)

        response = self.client.get(reverse("tickets:ticket_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.my_ticket.ticket_id)
        self.assertContains(response, self.overdue_ticket.ticket_id)
        self.assertNotContains(response, self.other_ticket.ticket_id)

    def test_management_can_view_all_tickets(self):
        self.client.force_login(self.management)

        response = self.client.get(reverse("tickets:ticket_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.my_ticket.ticket_id)
        self.assertContains(response, self.other_ticket.ticket_id)

    def test_department_user_can_create_general_support_ticket_without_asset(self):
        self.client.force_login(self.requester)

        response = self.client.post(
            reverse("tickets:ticket_create"),
            data={
                "title": "Password reset required",
                "description": "I cannot log in to the HR portal.",
                "ticket_category": FaultTicket.CATEGORY_ACCOUNT,
                "priority": FaultTicket.PRIORITY_MEDIUM,
            },
        )

        self.assertEqual(response.status_code, 302)
        ticket = FaultTicket.objects.get(title="Password reset required")
        self.assertEqual(ticket.reported_by, self.requester)
        self.assertEqual(ticket.department, self.ict_department)
        self.assertIsNone(ticket.asset)
        self.assertFalse(ticket.is_asset_fault)
        self.assertEqual(ticket.ticket_category, FaultTicket.CATEGORY_ACCOUNT)

    def test_ticket_list_htmx_returns_partial_markup(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("tickets:ticket_list"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ticket Queue")
        self.assertNotContains(response, "<html>", html=False)

    def test_overdue_queue_only_returns_overdue_tickets(self):
        self.client.force_login(self.help_desk)

        response = self.client.get(reverse("tickets:ticket_list"), {"queue": "overdue"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.overdue_ticket.ticket_id)
        self.assertNotContains(response, self.my_ticket.ticket_id)

    def test_ticket_asset_field_only_shows_assets_for_selected_department(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("tickets:ticket_asset_field"),
            {"department": self.ict_department.pk},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.asset.asset_tag)
        self.assertNotContains(response, self.finance_asset.asset_tag)

    def test_help_desk_workflow_update_triages_and_assigns_ticket(self):
        self.client.force_login(self.help_desk)
        due_date = (timezone.now() + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M")

        response = self.client.post(
            reverse("tickets:ticket_workflow_update", args=[self.my_ticket.pk]),
            data={
                "status": FaultTicket.STATUS_ASSIGNED,
                "impact": FaultTicket.IMPACT_DEPARTMENT,
                "assigned_to": self.technician.pk,
                "due_date": due_date,
                "requires_maintenance": "on",
                "escalated": "",
                "resolution_notes": "Triaged and handed off to field technician.",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.my_ticket.refresh_from_db()
        self.assertEqual(self.my_ticket.status, FaultTicket.STATUS_ASSIGNED)
        self.assertEqual(self.my_ticket.assigned_to, self.technician)
        self.assertEqual(self.my_ticket.triaged_by, self.help_desk)
        self.assertEqual(self.my_ticket.impact, FaultTicket.IMPACT_DEPARTMENT)
        self.assertTrue(self.my_ticket.requires_maintenance)
        self.assertIsNotNone(self.my_ticket.triaged_at)
        self.assertIsNotNone(self.my_ticket.assigned_at)
        self.assertIsNotNone(self.my_ticket.first_response_at)
        self.assertContains(response, "Workflow updated successfully.")

    def test_resolution_panel_marks_ticket_resolved(self):
        self.client.force_login(self.help_desk)

        response = self.client.post(
            reverse("tickets:ticket_resolution_update", args=[self.my_ticket.pk]),
            data={
                "resolution_summary": "Power adapter replaced and device booted normally.",
                "root_cause": "Faulty power adapter.",
                "action_taken": "Swapped adapter, tested charging, and confirmed startup.",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.my_ticket.refresh_from_db()
        resolution = TicketResolution.objects.get(ticket=self.my_ticket)
        self.assertEqual(self.my_ticket.status, FaultTicket.STATUS_RESOLVED)
        self.assertEqual(self.my_ticket.resolved_at, resolution.resolved_at)
        self.assertEqual(resolution.resolved_by, self.help_desk)
        self.assertContains(response, "Resolution saved and ticket marked resolved.")

    def test_ticket_attachment_upload_htmx_creates_attachment(self):
        self.client.force_login(self.requester)

        response = self.client.post(
            reverse("tickets:ticket_attachment_upload", args=[self.my_ticket.pk]),
            data={
                "file": SimpleUploadedFile(
                    "evidence.txt",
                    b"ticket attachment",
                    content_type="text/plain",
                ),
                "description": "Screenshot and issue notes",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(TicketAttachment.objects.filter(ticket=self.my_ticket).exists())
        self.assertContains(response, "Attachment uploaded successfully.")

    def test_create_maintenance_from_ticket_creates_asset_record(self):
        self.client.force_login(self.help_desk)

        response = self.client.post(
            reverse("tickets:ticket_create_maintenance", args=[self.my_ticket.pk]),
        )

        self.assertEqual(response.status_code, 302)
        record = MaintenanceRecord.objects.get(asset=self.asset)
        self.assertEqual(record.maintenance_type, MaintenanceRecord.TYPE_REPAIR)
        self.assertEqual(record.status, MaintenanceRecord.STATUS_OPEN)
        self.my_ticket.refresh_from_db()
        self.assertEqual(self.my_ticket.status, FaultTicket.STATUS_IN_PROGRESS)
        self.assertEqual(self.my_ticket.assigned_to, self.help_desk)
        self.assertTrue(self.my_ticket.requires_maintenance)

    def test_department_user_cannot_open_another_users_ticket(self):
        self.client.force_login(self.requester)

        response = self.client.get(reverse("tickets:ticket_detail", args=[self.other_ticket.pk]))

        self.assertEqual(response.status_code, 403)

    def test_ticket_detail_renders_for_untriaged_unassigned_ticket(self):
        self.client.force_login(self.requester)

        response = self.client.get(reverse("tickets:ticket_detail", args=[self.my_ticket.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Triaged By")
        self.assertContains(response, "Unassigned")

    def test_unassigned_technician_cannot_edit_workflow_for_visible_non_open_ticket(self):
        self.client.force_login(self.technician)

        response = self.client.get(
            reverse("tickets:ticket_update", args=[self.technician_reported_ticket.pk])
        )

        self.assertEqual(response.status_code, 403)
