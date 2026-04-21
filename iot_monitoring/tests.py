from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department
from assets.models import Asset, AssetCategory, AssetType

from .models import GPSReading, TrackerDevice


class GPSIngestViewTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="ICT", code="ICT")
        self.user = get_user_model().objects.create_user(
            email="iot-admin@example.com",
            password="password123",
            first_name="IoT",
            last_name="Admin",
            role="ADMIN",
        )
        self.category = AssetCategory.objects.get(name="Computers")
        self.asset_type = AssetType.objects.create(category=self.category, name="Tracker Laptop")
        self.asset = Asset.objects.create(
            asset_tag="IUIU-PR-001",
            name="Portable Tracker",
            category=self.category,
            asset_type=self.asset_type,
            department=self.department,
        )
        self.tracker = TrackerDevice.objects.create(
            asset=self.asset,
            device_id="IUIU-PR-001",
            api_key="abc123",
        )

    def test_gps_ingest_creates_reading_and_updates_tracker_last_seen(self):
        response = self.client.get(
            reverse("iot_monitoring:gps_ingest"),
            data={
                "id": self.tracker.device_id,
                "key": "abc123",
                "lat": "0.347596",
                "lon": "32.582520",
                "accuracy": "5.5",
                "speed": "12.3",
                "battery": "85",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "OK")
        self.assertEqual(GPSReading.objects.count(), 1)
        reading = GPSReading.objects.get()
        self.assertEqual(str(reading.latitude), "0.347596")
        self.assertEqual(str(reading.longitude), "32.582520")
        self.assertEqual(reading.accuracy_meters, 5.5)
        self.assertEqual(reading.speed_kmh, 12.3)
        self.assertEqual(reading.battery_level, 85)
        self.tracker.refresh_from_db()
        self.assertEqual(self.tracker.last_seen_at, reading.recorded_at)

    def test_gps_ingest_rejects_invalid_api_key(self):
        response = self.client.get(
            reverse("iot_monitoring:gps_ingest"),
            data={
                "id": self.tracker.device_id,
                "key": "wrong-key",
                "lat": "0.347596",
                "lon": "32.582520",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(GPSReading.objects.count(), 0)

    def test_asset_detail_view_shows_tracker_summary_and_recent_readings(self):
        reading = GPSReading.objects.create(
            device=self.tracker,
            latitude="0.347596",
            longitude="32.582520",
            accuracy_meters=4.1,
            battery_level=78,
            recorded_at=timezone.now(),
        )
        self.tracker.last_seen_at = reading.recorded_at
        self.tracker.save(update_fields=["last_seen_at"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("assets:asset_detail", args=[self.asset.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GPS Tracking")
        self.assertContains(response, self.tracker.device_id)
        self.assertContains(response, "GPS Map")
        self.assertContains(response, "Recent GPS Readings")
        self.assertContains(response, str(reading.latitude))
        self.assertContains(response, "View On Map")
        self.assertContains(response, "asset-gps-map")
        self.assertContains(response, 'hx-trigger="every 20s"')

    def test_asset_gps_partials_render_latest_tracker_data(self):
        reading = GPSReading.objects.create(
            device=self.tracker,
            latitude="0.347596",
            longitude="32.582520",
            speed_kmh=15.2,
            battery_level=81,
            recorded_at=timezone.now(),
        )
        self.tracker.last_seen_at = reading.recorded_at
        self.tracker.save(update_fields=["last_seen_at"])
        self.client.force_login(self.user)

        tracking_response = self.client.get(
            reverse("assets:asset_gps_tracking_card", args=[self.asset.pk])
        )
        map_response = self.client.get(
            reverse("assets:asset_gps_map_panel", args=[self.asset.pk])
        )

        self.assertEqual(tracking_response.status_code, 200)
        self.assertEqual(map_response.status_code, 200)
        self.assertContains(tracking_response, self.tracker.device_id)
        self.assertContains(tracking_response, "Auto-refresh 20s")
        self.assertContains(map_response, "Recent GPS Readings")
        self.assertContains(map_response, str(reading.latitude))
        self.assertContains(map_response, "asset-gps-map-points")
