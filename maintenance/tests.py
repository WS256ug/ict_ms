from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Department
from assets.models import Asset, AssetCategory, AssetType
from maintenance.models import MaintenanceLog, MaintenanceSchedule


class MaintenanceSignalTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.user = get_user_model().objects.create_user(
            email="tech@example.com",
            password="password123",
            first_name="Tech",
            last_name="User",
        )
        self.category = AssetCategory.objects.get(name="Networking")
        self.asset_type = AssetType.objects.create(category=self.category, name="Core Router")
        self.asset = Asset.objects.create(
            asset_tag="ASSET-100",
            name="Core Router",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
        )

    def test_maintenance_log_moves_asset_into_and_out_of_maintenance(self):
        next_maintenance_date = timezone.localdate() + timedelta(days=30)
        log = MaintenanceLog.objects.create(
            asset=self.asset,
            maintenance_type="CORRECTIVE",
            description="Replace power supply",
            performed_by=self.user,
            next_maintenance_date=next_maintenance_date,
        )

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_MAINTENANCE)
        self.assertTrue(
            MaintenanceSchedule.objects.filter(
                asset=self.asset,
                title="Corrective Maintenance Follow-up",
                scheduled_date=next_maintenance_date,
                is_completed=False,
            ).exists()
        )

        log.status = "COMPLETED"
        log.completed_at = timezone.now()
        log.save()

        self.asset.refresh_from_db()
        self.assertEqual(self.asset.status, Asset.STATUS_AVAILABLE)
