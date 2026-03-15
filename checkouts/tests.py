from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Department
from assets.models import Asset, AssetCategory
from notifications.models import Alert, Notification

from .models import CheckoutHistory, CheckoutRequest, GPSLocation, GeofenceAlert


class CheckoutFeatureTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.category = AssetCategory.objects.create(name="Computers")
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            email="admin@example.com",
            password="password123",
            first_name="Admin",
            last_name="User",
            role="ADMIN",
            department=self.department,
            is_staff=True,
        )
        self.requester = user_model.objects.create_user(
            email="requester@example.com",
            password="password123",
            first_name="Request",
            last_name="User",
            role="DEPARTMENT_USER",
            department=self.department,
        )
        self.asset = Asset.objects.create(
            asset_tag="AST-001",
            name="Portable Projector",
            category=self.category,
            department=self.department,
            current_location="ICT Office",
            status="ACTIVE",
            is_portable=True,
            max_checkout_days=7,
            has_gps_tracker=True,
            geofence_enabled=True,
            geofence_latitude=Decimal("0.347596"),
            geofence_longitude=Decimal("32.582520"),
            geofence_radius_meters=100,
            created_by=self.admin,
        )

    def create_checkout_request(self, **overrides):
        data = {
            "asset": self.asset,
            "requested_by": self.requester,
            "requester_department": self.department,
            "requester_phone": "+256700000001",
            "purpose": "Department presentation",
            "intended_location": "Main hall",
            "requested_checkout_date": timezone.localdate(),
            "requested_return_date": timezone.localdate() + timedelta(days=2),
        }
        data.update(overrides)
        return CheckoutRequest.objects.create(**data)

    def test_checkout_validation_respects_max_days(self):
        checkout = CheckoutRequest(
            asset=self.asset,
            requested_by=self.requester,
            requester_department=self.department,
            requester_phone="+256700000001",
            purpose="Field work",
            intended_location="Town campus",
            requested_checkout_date=timezone.localdate(),
            requested_return_date=timezone.localdate() + timedelta(days=10),
            status="PENDING",
        )

        with self.assertRaises(ValidationError):
            checkout.full_clean()

    def test_approved_checkout_blocks_asset_availability_and_creates_history(self):
        checkout = self.create_checkout_request()

        self.assertTrue(
            Notification.objects.filter(
                user=self.admin,
                title__startswith="New Checkout Request:",
            ).exists()
        )
        self.assertTrue(self.asset.is_available_for_checkout)

        checkout.status = "APPROVED"
        checkout.approved_by = self.admin
        checkout.approved_at = timezone.now()
        checkout._changed_by = self.admin
        checkout.save()

        self.asset.refresh_from_db()
        checkout.refresh_from_db()

        self.assertFalse(self.asset.is_available_for_checkout)
        self.assertEqual(self.asset.current_checkout, checkout)
        self.assertTrue(
            Notification.objects.filter(
                user=self.requester,
                title=f"Checkout Approved: {checkout.request_number}",
            ).exists()
        )
        self.assertTrue(
            CheckoutHistory.objects.filter(
                checkout=checkout,
                previous_status="PENDING",
                new_status="APPROVED",
                changed_by=self.admin,
            ).exists()
        )

    def test_geofence_exit_and_low_battery_generate_alerts(self):
        checkout = self.create_checkout_request(
            status="CHECKED_OUT",
            actual_checkout_date=timezone.now(),
            checked_out_by_admin=self.admin,
        )

        location = GPSLocation.objects.create(
            checkout=checkout,
            latitude=Decimal("0.360000"),
            longitude=Decimal("32.600000"),
            accuracy_meters=5.0,
            battery_level=10,
        )

        self.assertFalse(location.is_inside_geofence)
        self.assertGreater(location.distance_from_center_meters, self.asset.geofence_radius_meters)
        self.assertEqual(
            GeofenceAlert.objects.filter(checkout=checkout, alert_type="GEOFENCE_EXIT").count(),
            1,
        )
        self.assertEqual(
            GeofenceAlert.objects.filter(checkout=checkout, alert_type="LOW_BATTERY").count(),
            1,
        )
        self.assertTrue(
            Alert.objects.filter(title=f"Geofence Alert: {self.asset.asset_tag}").exists()
        )
        self.assertTrue(
            Alert.objects.filter(title=f"Low GPS Battery: {self.asset.asset_tag}").exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                title=f"Asset Left Geofence: {self.asset.asset_tag}",
                user=self.requester,
            ).exists()
        )
