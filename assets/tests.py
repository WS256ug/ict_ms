from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department
from assets.forms import AssetAssignmentForm, AssetForm
from assets.models import (
    Asset,
    AssetAssignment,
    AssetAttribute,
    AssetAttributeValue,
    AssetCategory,
    AssetDepreciation,
    AssetLocationHistory,
    AssetType,
    InstalledSoftware,
    Location,
    MaintenanceRecord,
    Software,
)


class AssetModelTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.user = get_user_model().objects.create_user(
            email="asset-admin@example.com",
            password="password123",
            first_name="Asset",
            last_name="Admin",
            role="ADMIN",
        )
        self.computer_category = AssetCategory.objects.get(name="Computers")
        self.projector_category = AssetCategory.objects.get(name="Projectors")
        self.laptop_type = AssetType.objects.create(category=self.computer_category, name="Laptop")
        self.projector_type = AssetType.objects.create(category=self.projector_category, name="Projector")

    def test_asset_category_name_must_match_defined_choices(self):
        category = AssetCategory(name="Router")

        with self.assertRaises(ValidationError):
            category.full_clean()

    def test_asset_type_must_match_category(self):
        asset = Asset(
            asset_tag="ASSET-001",
            name="Office Laptop",
            category=self.projector_category,
            asset_type=self.laptop_type,
            department=self.department,
        )

        with self.assertRaises(ValidationError):
            asset.full_clean()

    def test_current_value_uses_depreciation_record(self):
        asset = Asset.objects.create(
            asset_tag="ASSET-002",
            name="Office Laptop",
            category=self.computer_category,
            asset_type=self.laptop_type,
            department=self.department,
            purchase_date=timezone.localdate() - timedelta(days=365),
            purchase_cost=Decimal("1000.00"),
        )
        depreciation = AssetDepreciation.objects.create(
            asset=asset,
            purchase_cost=Decimal("1000.00"),
            useful_life_years=5,
            salvage_value=Decimal("100.00"),
            start_date=timezone.localdate() - timedelta(days=365),
        )

        self.assertEqual(asset.current_value, depreciation.current_value)
        self.assertLess(asset.current_value, Decimal("1000.00"))

    def test_location_history_updates_current_location(self):
        asset = Asset.objects.create(
            asset_tag="ASSET-003",
            name="Lecture Projector",
            category=self.projector_category,
            asset_type=self.projector_type,
            department=self.department,
        )
        location_one = Location.objects.create(name="Room 101")
        location_two = Location.objects.create(name="Room 202")

        AssetLocationHistory.objects.create(asset=asset, location=location_one, moved_by=self.user)
        AssetLocationHistory.objects.create(
            asset=asset,
            location=location_two,
            moved_by=self.user,
            moved_at=timezone.now() + timedelta(minutes=5),
        )

        self.assertEqual(asset.current_location, location_two)

    def test_assignment_and_maintenance_signals_refresh_asset_status(self):
        asset = Asset.objects.create(
            asset_tag="ASSET-004",
            name="Developer Laptop",
            category=self.computer_category,
            asset_type=self.laptop_type,
            department=self.department,
        )

        AssetAssignment.objects.create(
            asset=asset,
            assignee_identifier="ADM-001",
            assignee_name="Asset Admin",
            assignee_contact="asset-admin@example.com",
            assigned_date=timezone.localdate(),
            issued_by=self.user,
        )
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.STATUS_ASSIGNED)

        MaintenanceRecord.objects.create(
            asset=asset,
            issue_description="Battery issue",
            maintenance_type=MaintenanceRecord.TYPE_REPAIR,
            start_date=timezone.localdate(),
            status=MaintenanceRecord.STATUS_OPEN,
        )
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.STATUS_MAINTENANCE)

    def test_assignment_supports_purpose_and_condition_fields(self):
        asset = Asset.objects.create(
            asset_tag="ASSET-004A",
            name="Staff Laptop",
            category=self.computer_category,
            asset_type=self.laptop_type,
            department=self.department,
        )

        assignment = AssetAssignment.objects.create(
            asset=asset,
            assignee_identifier="STAFF-100",
            assignee_name="Field Officer",
            assignee_contact="0700000000",
            assigned_date=timezone.localdate(),
            issued_by=self.user,
            purpose="Field work",
            condition_at_issue="Good",
            condition_at_return="Fair",
            notes="Issued with charger",
        )

        self.assertEqual(assignment.purpose, "Field work")
        self.assertEqual(assignment.condition_at_issue, "Good")
        self.assertEqual(assignment.condition_at_return, "Fair")
        self.assertTrue(assignment.is_active)

    def test_assignment_form_requires_manual_assignee_details(self):
        asset = Asset.objects.create(
            asset_tag="ASSET-004B",
            name="Visitor Laptop",
            category=self.computer_category,
            asset_type=self.laptop_type,
            department=self.department,
        )
        form = AssetAssignmentForm(
            data={
                "asset": asset.pk,
                "assigned_date": str(timezone.localdate()),
                "issued_by": self.user.pk,
                "purpose": "Temporary use",
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("assignee_identifier", form.errors)
        self.assertIn("assignee_name", form.errors)
        self.assertIn("assignee_contact", form.errors)

    def test_installed_software_requires_computer_asset(self):
        asset = Asset.objects.create(
            asset_tag="ASSET-005",
            name="Lecture Projector",
            category=self.projector_category,
            asset_type=self.projector_type,
            department=self.department,
        )
        software = Software.objects.create(name="VLC", version="3.0")
        installation = InstalledSoftware(asset=asset, software=software)

        with self.assertRaises(ValidationError):
            installation.full_clean()


class AssetCrudViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.user = get_user_model().objects.create_user(
            email="admin@example.com",
            password="password123",
            first_name="Admin",
            last_name="User",
            role="ADMIN",
        )
        self.category = AssetCategory.objects.get(name="Computers")
        self.projector_category = AssetCategory.objects.get(name="Projectors")
        self.asset_type = AssetType.objects.create(category=self.category, name="Laptop")
        self.projector_type = AssetType.objects.create(category=self.projector_category, name="Projector")
        self.location = Location.objects.create(name="ICT Store")
        self.second_location = Location.objects.create(name="Lab 2")
        self.software_one = Software.objects.create(name="Microsoft Office", version="2024")
        self.software_two = Software.objects.create(name="VLC", version="3.0")
        self.processor_attribute = AssetAttribute.objects.create(
            category=self.category,
            name="Processor",
            field_type=AssetAttribute.FIELD_TEXT,
        )
        self.antivirus_attribute = AssetAttribute.objects.create(
            category=self.category,
            name="Antivirus Installed",
            field_type=AssetAttribute.FIELD_BOOLEAN,
        )
        self.projector_attribute = AssetAttribute.objects.create(
            category=self.projector_category,
            name="Lumens",
            field_type=AssetAttribute.FIELD_NUMBER,
        )
        self.asset = Asset.objects.create(
            asset_tag="ASSET-100",
            name="Demo Laptop",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
        )
        self.client.force_login(self.user)

    def test_asset_list_view_renders(self):
        response = self.client.get(reverse("assets:asset_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ASSET-100")

    def test_asset_form_includes_location_field(self):
        AssetLocationHistory.objects.create(asset=self.asset, location=self.location, moved_by=self.user)

        form = AssetForm(instance=self.asset, user=self.user)

        self.assertIn("location", form.fields)
        self.assertIn("purchase", form.fields)
        self.assertEqual(form._meta.model, Asset)
        self.assertEqual(form["location"].value(), self.location.pk)

    def test_asset_form_includes_selected_software_for_computer_assets(self):
        InstalledSoftware.objects.create(asset=self.asset, software=self.software_one, installed_by=self.user)

        form = AssetForm(instance=self.asset, user=self.user)

        self.assertIn("software", form.fields)
        self.assertTrue(form.show_software_field)
        self.assertIsInstance(form.fields["software"].widget, forms.MultipleHiddenInput)
        self.assertEqual([software.pk for software in form.selected_software_options], [self.software_one.pk])
        self.assertCountEqual(
            [software.pk for software in form.available_software_options],
            [self.software_two.pk],
        )
        self.assertCountEqual(
            [int(value) for value in form["software"].value()],
            [self.software_one.pk],
        )

    def test_asset_update_view_renders_add_selected_software_button(self):
        response = self.client.get(reverse("assets:asset_update", args=[self.asset.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add Selected Software")
        self.assertContains(response, "Software Added To This Asset")
        self.assertContains(response, "data-software-source-input")

    def test_asset_form_includes_existing_attribute_values_for_category(self):
        AssetAttributeValue.objects.create(
            asset=self.asset,
            attribute=self.processor_attribute,
            value="Intel Core i7",
        )
        AssetAttributeValue.objects.create(
            asset=self.asset,
            attribute=self.antivirus_attribute,
            value="Yes",
        )

        form = AssetForm(instance=self.asset, user=self.user)
        processor_field_name = AssetForm.attribute_field_name(self.processor_attribute.pk)
        antivirus_field_name = AssetForm.attribute_field_name(self.antivirus_attribute.pk)

        self.assertIn(processor_field_name, form.fields)
        self.assertIn(antivirus_field_name, form.fields)
        self.assertTrue(form.show_attribute_fields)
        self.assertEqual(form[processor_field_name].value(), "Intel Core i7")
        self.assertEqual(form[antivirus_field_name].value(), "true")

    def test_asset_create_view_creates_asset(self):
        response = self.client.post(
            reverse("assets:asset_create"),
            data={
                "asset_tag": "ASSET-101",
                "name": "New Laptop",
                "category": self.category.pk,
                "asset_type": self.asset_type.pk,
                "serial_number": "SER-101",
                "department": self.department.pk,
                "location": self.location.pk,
                "purchase": "",
                "purchase_date": "2026-03-13",
                "purchase_cost": "2500.00",
                "warranty_expiry": "2027-03-13",
                "status": Asset.STATUS_AVAILABLE,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Asset.objects.filter(asset_tag="ASSET-101").exists())
        asset = Asset.objects.get(asset_tag="ASSET-101")
        self.assertEqual(asset.current_location, self.location)
        self.assertTrue(
            AssetLocationHistory.objects.filter(
                asset=asset,
                location=self.location,
                moved_by=self.user,
            ).exists()
        )
        depreciation = AssetDepreciation.objects.get(asset__asset_tag="ASSET-101")
        self.assertEqual(depreciation.purchase_cost, Decimal("2500.00"))
        self.assertEqual(depreciation.useful_life_years, 5)
        self.assertEqual(depreciation.salvage_value, Decimal("0.00"))
        self.assertEqual(str(depreciation.start_date), "2026-03-13")

    def test_asset_create_view_saves_selected_software_for_computer_asset(self):
        response = self.client.post(
            reverse("assets:asset_create"),
            data={
                "asset_tag": "ASSET-101A",
                "name": "Software Laptop",
                "category": self.category.pk,
                "asset_type": self.asset_type.pk,
                "serial_number": "SER-101A",
                "department": self.department.pk,
                "location": self.location.pk,
                "software": [self.software_one.pk, self.software_two.pk],
                "purchase": "",
                "purchase_date": "",
                "purchase_cost": "",
                "warranty_expiry": "",
                "status": Asset.STATUS_AVAILABLE,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        asset = Asset.objects.get(asset_tag="ASSET-101A")
        self.assertCountEqual(
            InstalledSoftware.objects.filter(asset=asset).values_list("software_id", flat=True),
            [self.software_one.pk, self.software_two.pk],
        )
        self.assertTrue(
            InstalledSoftware.objects.filter(
                asset=asset,
                software=self.software_one,
                installed_by=self.user,
            ).exists()
        )

    def test_asset_detail_view_shows_installed_software_selected_on_asset(self):
        InstalledSoftware.objects.create(
            asset=self.asset,
            software=self.software_one,
            installed_by=self.user,
        )
        InstalledSoftware.objects.create(
            asset=self.asset,
            software=self.software_two,
            installed_by=self.user,
        )

        response = self.client.get(reverse("assets:asset_detail", args=[self.asset.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Installed Software")
        self.assertContains(response, str(self.software_one))
        self.assertContains(response, str(self.software_two))

    def test_asset_detail_view_shows_all_selected_software_for_asset(self):
        software_items = [
            Software.objects.create(name=f"Tool {index:02d}")
            for index in range(11)
        ]
        for software in software_items:
            InstalledSoftware.objects.create(
                asset=self.asset,
                software=software,
                installed_by=self.user,
            )

        response = self.client.get(reverse("assets:asset_detail", args=[self.asset.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tool 00")
        self.assertContains(response, "Tool 10")

    def test_asset_create_view_saves_category_attributes_for_computer_asset(self):
        response = self.client.post(
            reverse("assets:asset_create"),
            data={
                "asset_tag": "ASSET-101B",
                "name": "Configured Laptop",
                "category": self.category.pk,
                "asset_type": self.asset_type.pk,
                "serial_number": "SER-101B",
                "department": self.department.pk,
                "location": self.location.pk,
                "software": [self.software_one.pk],
                AssetForm.attribute_field_name(self.processor_attribute.pk): "Intel Core i5",
                AssetForm.attribute_field_name(self.antivirus_attribute.pk): "true",
                "purchase": "",
                "purchase_date": "",
                "purchase_cost": "",
                "warranty_expiry": "",
                "status": Asset.STATUS_AVAILABLE,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        asset = Asset.objects.get(asset_tag="ASSET-101B")
        self.assertTrue(
            AssetAttributeValue.objects.filter(
                asset=asset,
                attribute=self.processor_attribute,
                value="Intel Core i5",
            ).exists()
        )
        self.assertTrue(
            AssetAttributeValue.objects.filter(
                asset=asset,
                attribute=self.antivirus_attribute,
                value="Yes",
            ).exists()
        )

    def test_asset_update_view_updates_asset(self):
        AssetLocationHistory.objects.create(asset=self.asset, location=self.location, moved_by=self.user)

        response = self.client.post(
            reverse("assets:asset_update", args=[self.asset.pk]),
            data={
                "asset_tag": self.asset.asset_tag,
                "name": "Updated Laptop",
                "category": self.category.pk,
                "asset_type": self.asset_type.pk,
                "serial_number": "SER-UPDATED",
                "department": self.department.pk,
                "location": self.second_location.pk,
                "purchase": "",
                "purchase_date": "",
                "purchase_cost": "",
                "warranty_expiry": "",
                "status": Asset.STATUS_ASSIGNED,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.name, "Updated Laptop")
        self.assertEqual(self.asset.status, Asset.STATUS_ASSIGNED)
        self.assertEqual(self.asset.current_location, self.second_location)

    def test_asset_update_clears_software_when_category_changes_from_computer(self):
        InstalledSoftware.objects.create(asset=self.asset, software=self.software_one, installed_by=self.user)
        AssetAttributeValue.objects.create(
            asset=self.asset,
            attribute=self.processor_attribute,
            value="Intel Core i7",
        )

        response = self.client.post(
            reverse("assets:asset_update", args=[self.asset.pk]),
            data={
                "asset_tag": self.asset.asset_tag,
                "name": self.asset.name,
                "category": self.projector_category.pk,
                "asset_type": self.projector_type.pk,
                "serial_number": self.asset.serial_number,
                "department": self.department.pk,
                "location": self.location.pk,
                "purchase": "",
                "purchase_date": "",
                "purchase_cost": "",
                "warranty_expiry": "",
                "status": Asset.STATUS_AVAILABLE,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.category, self.projector_category)
        self.assertFalse(InstalledSoftware.objects.filter(asset=self.asset).exists())
        self.assertFalse(AssetAttributeValue.objects.filter(asset=self.asset).exists())

    def test_asset_update_view_updates_depreciation_record(self):
        response = self.client.post(
            reverse("assets:asset_update", args=[self.asset.pk]),
            data={
                "asset_tag": self.asset.asset_tag,
                "name": self.asset.name,
                "category": self.category.pk,
                "asset_type": self.asset_type.pk,
                "serial_number": self.asset.serial_number,
                "department": self.department.pk,
                "location": self.location.pk,
                "purchase": "",
                "purchase_date": "2026-03-01",
                "purchase_cost": "1800.00",
                "warranty_expiry": "",
                "useful_life_years": "4",
                "salvage_value": "200.00",
                "depreciation_start_date": "2026-03-10",
                "status": Asset.STATUS_AVAILABLE,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        depreciation = AssetDepreciation.objects.get(asset=self.asset)
        self.assertEqual(depreciation.purchase_cost, Decimal("1800.00"))
        self.assertEqual(depreciation.useful_life_years, 4)
        self.assertEqual(depreciation.salvage_value, Decimal("200.00"))
        self.assertEqual(str(depreciation.start_date), "2026-03-10")

    def test_asset_delete_view_removes_asset(self):
        get_response = self.client.get(reverse("assets:asset_delete", args=[self.asset.pk]))
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(reverse("assets:asset_delete", args=[self.asset.pk]))

        self.assertEqual(post_response.status_code, 302)
        self.assertFalse(Asset.objects.filter(pk=self.asset.pk).exists())

    def test_asset_list_htmx_returns_partial_content(self):
        response = self.client.get(
            reverse("assets:asset_list"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asset Register")
        self.assertNotContains(response, "<html>", html=False)

    def test_asset_type_field_returns_types_for_selected_category(self):
        other_category = AssetCategory.objects.get(name="Printers")
        AssetType.objects.create(category=other_category, name="Laser Printer")

        response = self.client.get(
            reverse("assets:asset_type_field"),
            {"category": self.category.pk},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Laptop")
        self.assertContains(response, "Installed Software")
        self.assertContains(response, "Processor")
        self.assertContains(response, "Antivirus Installed")
        self.assertNotContains(response, "Laser Printer")
        self.assertNotContains(response, "Lumens")


class SoftwareCrudViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.admin = get_user_model().objects.create_user(
            email="software-admin@example.com",
            password="password123",
            first_name="Software",
            last_name="Admin",
            role="ADMIN",
        )
        self.department_user = get_user_model().objects.create_user(
            email="software-user@example.com",
            password="password123",
            first_name="Software",
            last_name="User",
            role="DEPARTMENT_USER",
        )
        self.category = AssetCategory.objects.get(name="Computers")
        self.asset_type = AssetType.objects.create(category=self.category, name="Desktop")
        self.asset = Asset.objects.create(
            asset_tag="ASSET-SW-001",
            name="Software Desktop",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
        )
        self.software = Software.objects.create(name="Windows 11", version="23H2", vendor="Microsoft")
        self.client.force_login(self.admin)

    def test_software_list_view_renders(self):
        response = self.client.get(reverse("assets:software_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Software Catalog")
        self.assertContains(response, "Windows 11")

    def test_software_detail_view_shows_installations(self):
        InstalledSoftware.objects.create(
            asset=self.asset,
            software=self.software,
            installed_by=self.admin,
        )

        response = self.client.get(reverse("assets:software_detail", args=[self.software.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Installed On Assets")
        self.assertContains(response, self.asset.asset_tag)

    def test_software_create_view_creates_software(self):
        response = self.client.post(
            reverse("assets:software_create"),
            data={
                "name": "LibreOffice",
                "version": "24.2",
                "vendor": "The Document Foundation",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Software.objects.filter(name="LibreOffice", version="24.2").exists())

    def test_software_update_view_updates_software(self):
        response = self.client.post(
            reverse("assets:software_update", args=[self.software.pk]),
            data={
                "name": "Windows 11 Pro",
                "version": "24H2",
                "vendor": "Microsoft",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.software.refresh_from_db()
        self.assertEqual(self.software.name, "Windows 11 Pro")
        self.assertEqual(self.software.version, "24H2")

    def test_software_delete_view_removes_software_and_installations(self):
        InstalledSoftware.objects.create(
            asset=self.asset,
            software=self.software,
            installed_by=self.admin,
        )

        get_response = self.client.get(reverse("assets:software_delete", args=[self.software.pk]))
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(reverse("assets:software_delete", args=[self.software.pk]))

        self.assertEqual(post_response.status_code, 302)
        self.assertFalse(Software.objects.filter(pk=self.software.pk).exists())
        self.assertFalse(InstalledSoftware.objects.filter(asset=self.asset).exists())

    def test_department_user_cannot_create_software(self):
        self.client.force_login(self.department_user)

        response = self.client.get(reverse("assets:software_create"))

        self.assertEqual(response.status_code, 403)


class LocationCrudViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.admin = get_user_model().objects.create_user(
            email="location-admin@example.com",
            password="password123",
            first_name="Location",
            last_name="Admin",
            role="ADMIN",
            department=self.department,
        )
        self.technician = get_user_model().objects.create_user(
            email="location-tech@example.com",
            password="password123",
            first_name="Location",
            last_name="Tech",
            role="TECHNICIAN",
            department=self.department,
        )
        self.category = AssetCategory.objects.get(name="Computers")
        self.asset_type = AssetType.objects.create(category=self.category, name="Notebook")
        self.location = Location.objects.create(name="Main Store", building="Block A", room="1")
        self.client.force_login(self.admin)

    def test_admin_can_open_location_list(self):
        response = self.client.get(reverse("assets:location_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Locations")
        self.assertContains(response, "Main Store")

    def test_non_admin_cannot_open_location_management(self):
        self.client.force_login(self.technician)

        response = self.client.get(reverse("assets:location_list"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_update_and_delete_unused_location(self):
        create_response = self.client.post(
            reverse("assets:location_create"),
            data={
                "name": "Lab 1",
                "building": "Science Block",
                "room": "12",
                "description": "Computer laboratory",
            },
        )

        self.assertEqual(create_response.status_code, 302)
        location = Location.objects.get(name="Lab 1")
        self.assertEqual(location.building, "Science Block")

        update_response = self.client.post(
            reverse("assets:location_update", args=[location.pk]),
            data={
                "name": "Lab 1",
                "building": "Technology Block",
                "room": "14",
                "description": "Updated lab location",
            },
        )

        self.assertEqual(update_response.status_code, 302)
        location.refresh_from_db()
        self.assertEqual(location.building, "Technology Block")
        self.assertEqual(location.room, "14")

        delete_response = self.client.post(reverse("assets:location_delete", args=[location.pk]))

        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(Location.objects.filter(pk=location.pk).exists())

    def test_location_delete_is_blocked_when_history_exists(self):
        asset = Asset.objects.create(
            asset_tag="ASSET-150",
            name="Tracked Laptop",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
        )
        AssetLocationHistory.objects.create(asset=asset, location=self.location, moved_by=self.admin)

        response = self.client.post(reverse("assets:location_delete", args=[self.location.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Location.objects.filter(pk=self.location.pk).exists())
        self.assertContains(response, "cannot be deleted")


class AssetAssignmentCrudViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.admin = get_user_model().objects.create_user(
            email="assignment-admin@example.com",
            password="password123",
            first_name="Assignment",
            last_name="Admin",
            role="ADMIN",
        )
        self.assignee = get_user_model().objects.create_user(
            email="assignment-user@example.com",
            password="password123",
            first_name="Assigned",
            last_name="User",
            role="DEPARTMENT_USER",
        )
        self.category = AssetCategory.objects.get(name="Computers")
        self.asset_type = AssetType.objects.create(category=self.category, name="Desktop")
        self.asset = Asset.objects.create(
            asset_tag="ASSET-200",
            name="Assigned Desktop",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
        )
        self.client.force_login(self.admin)

    def test_assignment_list_view_renders(self):
        AssetAssignment.objects.create(
            asset=self.asset,
            assignee_identifier="EMP-200",
            assignee_name="Assigned User",
            assignee_contact="assignment-user@example.com",
            assigned_date=timezone.localdate(),
            issued_by=self.admin,
            purpose="Office work",
        )

        response = self.client.get(reverse("assets:assignment_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asset Assignments")
        self.assertContains(response, self.asset.asset_tag)

    def test_assignment_detail_view_renders(self):
        assignment = AssetAssignment.objects.create(
            asset=self.asset,
            assignee_identifier="EMP-201",
            assignee_name="Assigned User",
            assignee_contact="assignment-user@example.com",
            assigned_date=timezone.localdate(),
            issued_by=self.admin,
            purpose="Office work",
        )

        response = self.client.get(reverse("assets:assignment_detail", args=[assignment.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Office work")
        self.assertContains(response, self.asset.asset_tag)

    def test_assignment_create_view_creates_assignment(self):
        response = self.client.post(
            reverse("assets:assignment_create"),
            data={
                "asset": self.asset.pk,
                "assignee_identifier": "EMP-202",
                "assignee_name": "Assigned User",
                "assignee_contact": "assignment-user@example.com",
                "assigned_date": "2026-03-15",
                "expected_return": "2026-03-22",
                "returned_date": "",
                "issued_by": self.admin.pk,
                "purpose": "Office work",
                "condition_at_issue": "Good",
                "condition_at_return": "",
                "notes": "Issued with mouse and keyboard",
            },
        )

        self.assertEqual(response.status_code, 302)
        assignment = AssetAssignment.objects.get(asset=self.asset, assignee_identifier="EMP-202")
        self.assertEqual(assignment.purpose, "Office work")
        self.assertEqual(assignment.condition_at_issue, "Good")
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_ASSIGNED)

    def test_assignment_update_view_updates_assignment(self):
        assignment = AssetAssignment.objects.create(
            asset=self.asset,
            assignee_identifier="EMP-203",
            assignee_name="Assigned User",
            assignee_contact="assignment-user@example.com",
            assigned_date=timezone.localdate(),
            expected_return=timezone.localdate() + timedelta(days=7),
            issued_by=self.admin,
            purpose="Office work",
            condition_at_issue="Good",
        )
        returned_date = assignment.assigned_date + timedelta(days=1)

        response = self.client.post(
            reverse("assets:assignment_update", args=[assignment.pk]),
            data={
                "asset": self.asset.pk,
                "assignee_identifier": "EMP-203",
                "assignee_name": "Assigned User",
                "assignee_contact": "0700000001",
                "assigned_date": str(assignment.assigned_date),
                "expected_return": str(assignment.expected_return),
                "returned_date": str(returned_date),
                "issued_by": self.admin.pk,
                "purpose": "Returned after project",
                "condition_at_issue": "Good",
                "condition_at_return": "Fair",
                "notes": "Returned with minor wear",
            },
        )

        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.purpose, "Returned after project")
        self.assertEqual(assignment.assignee_contact, "0700000001")
        self.assertEqual(assignment.condition_at_return, "Fair")
        self.assertEqual(assignment.returned_date, returned_date)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_AVAILABLE)

    def test_assignment_delete_view_removes_assignment(self):
        assignment = AssetAssignment.objects.create(
            asset=self.asset,
            assignee_identifier="EMP-204",
            assignee_name="Assigned User",
            assignee_contact="assignment-user@example.com",
            assigned_date=timezone.localdate(),
            issued_by=self.admin,
            purpose="Office work",
        )

        get_response = self.client.get(reverse("assets:assignment_delete", args=[assignment.pk]))
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(reverse("assets:assignment_delete", args=[assignment.pk]))

        self.assertEqual(post_response.status_code, 302)
        self.assertFalse(AssetAssignment.objects.filter(pk=assignment.pk).exists())
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_AVAILABLE)


class MaintenanceCrudViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.admin = get_user_model().objects.create_user(
            email="maintenance-admin@example.com",
            password="password123",
            first_name="Maintenance",
            last_name="Admin",
            role="ADMIN",
        )
        self.category = AssetCategory.objects.get(name="Computers")
        self.asset_type = AssetType.objects.create(category=self.category, name="Workstation")
        self.asset = Asset.objects.create(
            asset_tag="ASSET-300",
            name="Office Workstation",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
        )
        self.client.force_login(self.admin)

    def test_maintenance_list_view_renders(self):
        MaintenanceRecord.objects.create(
            asset=self.asset,
            issue_description="Routine inspection",
            maintenance_type=MaintenanceRecord.TYPE_INSPECTION,
            start_date=timezone.localdate(),
            status=MaintenanceRecord.STATUS_OPEN,
            technician="Maintenance Admin",
        )

        response = self.client.get(reverse("assets:maintenance_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Maintenance Records")
        self.assertContains(response, self.asset.asset_tag)

    def test_maintenance_create_view_creates_record_and_sets_asset_status(self):
        response = self.client.post(
            reverse("assets:maintenance_create"),
            data={
                "asset": self.asset.pk,
                "issue_description": "Fan replacement",
                "maintenance_type": MaintenanceRecord.TYPE_REPAIR,
                "start_date": "2026-03-15",
                "end_date": "",
                "technician": "Maintenance Admin",
                "cost": "150.00",
                "status": MaintenanceRecord.STATUS_IN_PROGRESS,
                "notes": "Waiting for parts",
            },
        )

        self.assertEqual(response.status_code, 302)
        record = MaintenanceRecord.objects.get(asset=self.asset, technician="Maintenance Admin")
        self.assertEqual(record.status, MaintenanceRecord.STATUS_IN_PROGRESS)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_MAINTENANCE)

    def test_maintenance_update_view_completed_sets_asset_status_available(self):
        record = MaintenanceRecord.objects.create(
            asset=self.asset,
            issue_description="Battery issue",
            maintenance_type=MaintenanceRecord.TYPE_REPAIR,
            start_date=timezone.localdate(),
            status=MaintenanceRecord.STATUS_OPEN,
            technician="Maintenance Admin",
        )
        end_date = record.start_date + timedelta(days=1)

        response = self.client.post(
            reverse("assets:maintenance_update", args=[record.pk]),
            data={
                "asset": self.asset.pk,
                "issue_description": "Battery replaced",
                "maintenance_type": MaintenanceRecord.TYPE_REPAIR,
                "start_date": str(record.start_date),
                "end_date": str(end_date),
                "technician": "Maintenance Admin",
                "cost": "200.00",
                "status": MaintenanceRecord.STATUS_COMPLETED,
                "notes": "Device tested successfully",
            },
        )

        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, MaintenanceRecord.STATUS_COMPLETED)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_AVAILABLE)

    def test_completed_maintenance_restores_assigned_status_when_assignment_exists(self):
        AssetAssignment.objects.create(
            asset=self.asset,
            assignee_identifier="EMP-301",
            assignee_name="Assigned User",
            assignee_contact="assigned@example.com",
            assigned_date=timezone.localdate(),
            issued_by=self.admin,
        )
        record = MaintenanceRecord.objects.create(
            asset=self.asset,
            issue_description="Operating system reinstall",
            maintenance_type=MaintenanceRecord.TYPE_UPGRADE,
            start_date=timezone.localdate(),
            status=MaintenanceRecord.STATUS_IN_PROGRESS,
            technician="Maintenance Admin",
        )
        end_date = record.start_date + timedelta(days=1)

        response = self.client.post(
            reverse("assets:maintenance_update", args=[record.pk]),
            data={
                "asset": self.asset.pk,
                "issue_description": "Operating system reinstalled",
                "maintenance_type": MaintenanceRecord.TYPE_UPGRADE,
                "start_date": str(record.start_date),
                "end_date": str(end_date),
                "technician": "Maintenance Admin",
                "cost": "",
                "status": MaintenanceRecord.STATUS_COMPLETED,
                "notes": "Returned to user",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_ASSIGNED)

    def test_maintenance_delete_view_recalculates_asset_status(self):
        record = MaintenanceRecord.objects.create(
            asset=self.asset,
            issue_description="Routine service",
            maintenance_type=MaintenanceRecord.TYPE_INSPECTION,
            start_date=timezone.localdate(),
            status=MaintenanceRecord.STATUS_OPEN,
            technician="Maintenance Admin",
        )

        get_response = self.client.get(reverse("assets:maintenance_delete", args=[record.pk]))
        self.assertEqual(get_response.status_code, 200)

        post_response = self.client.post(reverse("assets:maintenance_delete", args=[record.pk]))

        self.assertEqual(post_response.status_code, 302)
        self.assertFalse(MaintenanceRecord.objects.filter(pk=record.pk).exists())
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_AVAILABLE)
