from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department
from assets.models import (
    Asset,
    AssetAssignment,
    AssetAudit,
    AssetAuditItem,
    AssetCategory,
    AssetDepreciation,
    AssetLocationHistory,
    AssetType,
    InstalledSoftware,
    Location,
    MaintenanceRecord,
    Software,
)
from tickets.models import FaultTicket, TicketResolution


class ReportViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.operations_department = Department.objects.create(
            name="Operations",
            code="OPS",
        )
        self.user = get_user_model().objects.create_user(
            email="reports-admin@example.com",
            password="password123",
            first_name="Report",
            last_name="Admin",
            role="ADMIN",
            department=self.department,
        )
        self.technician = get_user_model().objects.create_user(
            email="report-tech@example.com",
            password="password123",
            first_name="Alex",
            last_name="Technician",
            role="TECHNICIAN",
            department=self.department,
        )
        self.department_user = get_user_model().objects.create_user(
            email="report-user@example.com",
            password="password123",
            first_name="Desk",
            last_name="Reporter",
            role="DEPARTMENT_USER",
            department=self.department,
        )
        self.other_department_user = get_user_model().objects.create_user(
            email="ops-user@example.com",
            password="password123",
            first_name="Ops",
            last_name="Reporter",
            role="DEPARTMENT_USER",
            department=self.operations_department,
        )

        self.category = AssetCategory.objects.get(name="Computers")
        self.asset_type = AssetType.objects.create(category=self.category, name="Laptop")
        self.primary_location = Location.objects.create(
            name="ICT Store",
            building="Main Block",
            room="12",
        )
        self.secondary_location = Location.objects.create(
            name="Operations Office",
            building="Admin Block",
            room="3",
        )

        self.assigned_asset = Asset.objects.create(
            asset_tag="ASSET-REPORT-001",
            name="Assigned Laptop",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
            purchase_date=timezone.localdate() - timedelta(days=600),
            purchase_cost=Decimal("1500.00"),
        )
        self.maintenance_asset = Asset.objects.create(
            asset_tag="ASSET-REPORT-002",
            name="Maintenance Laptop",
            category=self.category,
            asset_type=self.asset_type,
            department=self.operations_department,
            purchase_date=timezone.localdate() - timedelta(days=900),
            purchase_cost=Decimal("1800.00"),
        )

        AssetLocationHistory.objects.create(
            asset=self.assigned_asset,
            location=self.primary_location,
            moved_by=self.user,
        )
        AssetLocationHistory.objects.create(
            asset=self.maintenance_asset,
            location=self.secondary_location,
            moved_by=self.user,
        )

        self.assignment = AssetAssignment.objects.create(
            asset=self.assigned_asset,
            assignee_identifier="EMP-100",
            assignee_name="Jane Holder",
            assignee_contact="0700000000",
            assigned_date=timezone.localdate() - timedelta(days=8),
            expected_return=timezone.localdate() - timedelta(days=2),
            issued_by=self.user,
            purpose="Field visits",
        )
        self.maintenance = MaintenanceRecord.objects.create(
            asset=self.maintenance_asset,
            issue_description="Keyboard replacement",
            maintenance_type=MaintenanceRecord.TYPE_REPAIR,
            start_date=timezone.localdate() - timedelta(days=3),
            technician="Alex Technician",
            cost=Decimal("125.00"),
            status=MaintenanceRecord.STATUS_OPEN,
        )
        self.software = Software.objects.create(
            name="Office Suite",
            version="2026",
            vendor="Open Productivity",
        )
        self.installation = InstalledSoftware.objects.create(
            asset=self.maintenance_asset,
            software=self.software,
            installed_date=timezone.localdate() - timedelta(days=30),
            installed_by=self.user,
        )
        self.depreciation = AssetDepreciation.objects.create(
            asset=self.maintenance_asset,
            purchase_cost=Decimal("1800.00"),
            useful_life_years=5,
            salvage_value=Decimal("300.00"),
            start_date=timezone.localdate() - timedelta(days=730),
        )
        self.audit = AssetAudit.objects.create(
            audit_date=timezone.localdate() - timedelta(days=1),
            conducted_by=self.user,
            notes="Quarterly audit",
        )
        AssetAuditItem.objects.create(
            audit=self.audit,
            asset=self.assigned_asset,
            status=AssetAuditItem.STATUS_MISSING,
            notes="Issued but not presented",
        )
        AssetAuditItem.objects.create(
            audit=self.audit,
            asset=self.maintenance_asset,
            status=AssetAuditItem.STATUS_FOUND,
            notes="In workshop",
        )

        self.open_ticket = FaultTicket.objects.create(
            title="Laptop not booting",
            description="User reports the laptop does not boot.",
            ticket_category=FaultTicket.CATEGORY_HARDWARE,
            is_asset_fault=True,
            asset=self.assigned_asset,
            department=self.department,
            reported_by=self.department_user,
            assigned_to=self.technician,
            status=FaultTicket.STATUS_IN_PROGRESS,
            priority=FaultTicket.PRIORITY_CRITICAL,
            due_date=timezone.now() - timedelta(hours=2),
            requires_maintenance=True,
        )
        self.resolved_ticket = FaultTicket.objects.create(
            title="Password reset",
            description="Reset account for operations staff member.",
            ticket_category=FaultTicket.CATEGORY_ACCOUNT,
            department=self.operations_department,
            reported_by=self.other_department_user,
            assigned_to=self.technician,
            status=FaultTicket.STATUS_RESOLVED,
            priority=FaultTicket.PRIORITY_MEDIUM,
            first_response_at=timezone.now() - timedelta(hours=3),
            resolved_at=timezone.now() - timedelta(hours=1),
        )
        TicketResolution.objects.create(
            ticket=self.resolved_ticket,
            resolution_summary="Password reset and verified.",
            root_cause="Expired credentials.",
            action_taken="Reset password and confirmed login.",
            resolved_by=self.user,
            resolved_at=self.resolved_ticket.resolved_at,
        )

        self.report_pages = {
            "reports:index": "Operations Reports",
            "reports:ticket_report": "Ticket Report",
            "reports:asset_inventory": "Asset Inventory",
            "reports:assets_by_department": "Assets by Department",
            "reports:assets_by_location": "Assets by Location",
            "reports:assigned_assets": "Assigned Assets",
            "reports:maintenance_report": "Maintenance Report",
            "reports:software_inventory": "Software Inventory",
            "reports:depreciation_report": "Depreciation Report",
            "reports:audit_report": "Audit Report",
        }
        self.exportable_pages = [
            "reports:ticket_report",
            "reports:asset_inventory",
            "reports:assets_by_department",
            "reports:assets_by_location",
            "reports:assigned_assets",
            "reports:maintenance_report",
            "reports:software_inventory",
            "reports:depreciation_report",
            "reports:audit_report",
        ]

    def test_report_pages_require_login(self):
        for url_name in self.report_pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertRedirects(
                    response,
                    f"{reverse('login')}?next={reverse(url_name)}",
                )

    def test_report_pages_render_for_authenticated_users(self):
        self.client.force_login(self.user)

        for url_name, heading in self.report_pages.items():
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, heading)

    def test_report_pages_include_expected_asset_and_ticket_data(self):
        self.client.force_login(self.user)

        ticket_response = self.client.get(reverse("reports:ticket_report"))
        self.assertContains(ticket_response, self.open_ticket.ticket_id)
        self.assertContains(ticket_response, "Hardware Fault")
        self.assertContains(ticket_response, self.assigned_asset.asset_tag)
        self.assertContains(ticket_response, self.technician.get_full_name())

        inventory_response = self.client.get(reverse("reports:asset_inventory"))
        self.assertContains(inventory_response, self.assigned_asset.asset_tag)
        self.assertContains(inventory_response, "ICT Store")

        department_response = self.client.get(reverse("reports:assets_by_department"))
        self.assertContains(department_response, self.department.name)
        self.assertContains(department_response, self.operations_department.name)

        location_response = self.client.get(reverse("reports:assets_by_location"))
        self.assertContains(location_response, "Operations Office")

        assigned_response = self.client.get(reverse("reports:assigned_assets"))
        self.assertContains(assigned_response, self.assignment.assignee_name)
        self.assertContains(assigned_response, self.assignment.assignee_identifier)

        maintenance_response = self.client.get(reverse("reports:maintenance_report"))
        self.assertContains(maintenance_response, self.maintenance.technician)
        self.assertContains(maintenance_response, self.maintenance.issue_description)

        software_response = self.client.get(reverse("reports:software_inventory"))
        self.assertContains(software_response, self.software.name)
        self.assertContains(software_response, self.installation.asset.asset_tag)

        depreciation_response = self.client.get(reverse("reports:depreciation_report"))
        self.assertContains(depreciation_response, self.depreciation.asset.asset_tag)

        audit_response = self.client.get(reverse("reports:audit_report"))
        self.assertContains(audit_response, self.assigned_asset.asset_tag)
        self.assertContains(audit_response, "Missing")

    def test_ticket_report_respects_ticket_visibility(self):
        self.client.force_login(self.department_user)

        response = self.client.get(reverse("reports:ticket_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.open_ticket.ticket_id)
        self.assertNotContains(response, self.resolved_ticket.ticket_id)

    def test_report_pages_support_csv_downloads(self):
        self.client.force_login(self.user)

        for url_name in self.exportable_pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name), {"export": "csv"})
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/csv", response["Content-Type"])
                self.assertIn("attachment;", response["Content-Disposition"])

        ticket_csv = self.client.get(
            reverse("reports:ticket_report"),
            {"export": "csv"},
        )
        self.assertContains(ticket_csv, self.open_ticket.ticket_id)
        self.assertContains(ticket_csv, "Ticket ID")

    def test_report_pages_support_pdf_downloads(self):
        self.client.force_login(self.user)

        for url_name in self.exportable_pages:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name), {"export": "pdf"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/pdf")
                self.assertIn("attachment;", response["Content-Disposition"])
                self.assertTrue(response.content.startswith(b"%PDF-1.4"))
