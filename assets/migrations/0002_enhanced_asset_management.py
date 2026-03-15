from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def move_disposed_assets_to_retired(apps, schema_editor):
    Asset = apps.get_model("assets", "Asset")
    Asset.objects.filter(status="DISPOSED").update(status="RETIRED")


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="assetcategory",
            name="default_depreciation_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("20.00"),
                help_text="Default annual depreciation rate (%) for this category",
                max_digits=5,
            ),
        ),
        migrations.RenameField(
            model_name="asset",
            old_name="location",
            new_name="current_location",
        ),
        migrations.AddField(
            model_name="asset",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True,
                help_text="Person currently using this asset",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_assets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_assets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="depreciation_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Annual depreciation rate (%). Leave blank to use category default.",
                max_digits=5,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="last_serviced",
            field=models.DateField(
                blank=True,
                help_text="Date of last maintenance/service",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="next_service_due",
            field=models.DateField(
                blank=True,
                help_text="Next scheduled service date",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="asset",
            name="current_location",
            field=models.CharField(
                help_text="Physical location (e.g., Room 204)",
                max_length=200,
            ),
        ),
        migrations.AlterField(
            model_name="asset",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assets",
                to="accounts.department",
            ),
        ),
        migrations.AlterField(
            model_name="asset",
            name="status",
            field=models.CharField(
                choices=[
                    ("ACTIVE", "Active"),
                    ("UNDER_MAINTENANCE", "Under Maintenance"),
                    ("FAULTY", "Faulty"),
                    ("RETIRED", "Retired"),
                    ("IN_STORAGE", "In Storage"),
                ],
                default="ACTIVE",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="AssetLocationHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_location", models.CharField(max_length=200)),
                ("new_location", models.CharField(max_length=200)),
                ("reason", models.TextField(blank=True, help_text="Reason for relocation", null=True)),
                ("moved_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="location_history", to="assets.asset"),
                ),
                (
                    "moved_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
                ),
                (
                    "new_department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="new_locations",
                        to="accounts.department",
                    ),
                ),
                (
                    "previous_department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="previous_locations",
                        to="accounts.department",
                    ),
                ),
            ],
            options={
                "verbose_name": "Asset Location History",
                "verbose_name_plural": "Asset Location Histories",
                "ordering": ["-moved_at"],
            },
        ),
        migrations.CreateModel(
            name="AssetStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_status", models.CharField(max_length=20)),
                ("new_status", models.CharField(max_length=20)),
                ("reason", models.TextField(blank=True, null=True)),
                ("changed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_history", to="assets.asset"),
                ),
                (
                    "changed_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Asset Status History",
                "verbose_name_plural": "Asset Status Histories",
                "ordering": ["-changed_at"],
            },
        ),
        migrations.CreateModel(
            name="ComputerAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("computer_type", models.CharField(choices=[("DESKTOP", "Desktop Computer"), ("LAPTOP", "Laptop"), ("SERVER", "Server"), ("WORKSTATION", "Workstation")], max_length=20)),
                ("processor", models.CharField(blank=True, help_text="e.g., Intel Core i5-10400", max_length=200, null=True)),
                ("ram_gb", models.IntegerField(blank=True, help_text="RAM in GB", null=True)),
                ("storage_gb", models.IntegerField(blank=True, help_text="Storage capacity in GB", null=True)),
                ("storage_type", models.CharField(blank=True, help_text="e.g., SSD, HDD, NVMe", max_length=50, null=True)),
                ("operating_system", models.CharField(choices=[("WINDOWS_11", "Windows 11"), ("WINDOWS_10", "Windows 10"), ("WINDOWS_SERVER_2022", "Windows Server 2022"), ("UBUNTU_22_04", "Ubuntu 22.04"), ("UBUNTU_20_04", "Ubuntu 20.04"), ("MACOS", "macOS"), ("OTHER", "Other")], default="WINDOWS_10", max_length=50)),
                ("os_license_key", models.CharField(blank=True, help_text="Windows/OS license key", max_length=100, null=True)),
                ("hostname", models.CharField(blank=True, max_length=100, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("mac_address", models.CharField(blank=True, help_text="Format: AA:BB:CC:DD:EE:FF", max_length=17, null=True)),
                ("computer_name", models.CharField(blank=True, help_text="Windows computer name", max_length=100, null=True)),
                ("domain_joined", models.BooleanField(default=False, help_text="Is computer joined to domain?")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="computer_details", to="assets.asset"),
                ),
            ],
            options={
                "verbose_name": "Computer Asset Details",
                "verbose_name_plural": "Computer Asset Details",
            },
        ),
        migrations.CreateModel(
            name="InstalledSoftware",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("software_name", models.CharField(max_length=200)),
                ("version", models.CharField(blank=True, max_length=100, null=True)),
                ("publisher", models.CharField(blank=True, max_length=200, null=True)),
                ("license_type", models.CharField(choices=[("LICENSED", "Licensed"), ("FREE", "Free/Open Source"), ("TRIAL", "Trial"), ("SUBSCRIPTION", "Subscription")], default="FREE", max_length=20)),
                ("license_key", models.CharField(blank=True, max_length=200, null=True)),
                ("license_expiry", models.DateField(blank=True, help_text="For subscription/trial software", null=True)),
                ("installed_date", models.DateField(default=django.utils.timezone.localdate)),
                ("is_active", models.BooleanField(default=True, help_text="Is software currently installed?")),
                ("uninstalled_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "computer",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="installed_software", to="assets.computerasset"),
                ),
                (
                    "installed_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Installed Software",
                "verbose_name_plural": "Installed Software",
                "ordering": ["software_name"],
                "unique_together": {("computer", "software_name", "version")},
            },
        ),
        migrations.AddIndex(
            model_name="asset",
            index=models.Index(fields=["category"], name="assets_asse_categor_7db38a_idx"),
        ),
        migrations.RunPython(move_disposed_assets_to_retired, migrations.RunPython.noop),
    ]
