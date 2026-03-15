from django.db import migrations, models


def migrate_installed_software_to_catalog(apps, schema_editor):
    ComputerAsset = apps.get_model("assets", "ComputerAsset")
    InstalledSoftware = apps.get_model("assets", "InstalledSoftware")
    Software = apps.get_model("assets", "Software")
    through_model = ComputerAsset.software.through

    for installed in InstalledSoftware.objects.all().iterator():
        software, _ = Software.objects.get_or_create(
            software_name=installed.software_name,
            version=installed.version,
            publisher=installed.publisher,
            defaults={
                "license_type": installed.license_type,
                "license_key": installed.license_key,
                "license_expiry": installed.license_expiry,
                "notes": installed.notes,
            },
        )

        updates = []
        if not software.license_key and installed.license_key:
            software.license_key = installed.license_key
            updates.append("license_key")
        if not software.license_expiry and installed.license_expiry:
            software.license_expiry = installed.license_expiry
            updates.append("license_expiry")
        if not software.notes and installed.notes:
            software.notes = installed.notes
            updates.append("notes")
        if updates:
            software.save(update_fields=updates)

        through_model.objects.get_or_create(
            computerasset_id=installed.computer_id,
            software_id=software.id,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_enhanced_asset_management"),
    ]

    operations = [
        migrations.CreateModel(
            name="Software",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("software_name", models.CharField(max_length=200)),
                ("version", models.CharField(blank=True, max_length=100, null=True)),
                ("publisher", models.CharField(blank=True, max_length=200, null=True)),
                ("license_type", models.CharField(choices=[("LICENSED", "Licensed"), ("FREE", "Free/Open Source"), ("TRIAL", "Trial"), ("SUBSCRIPTION", "Subscription")], default="FREE", max_length=20)),
                ("license_key", models.CharField(blank=True, max_length=200, null=True)),
                ("license_expiry", models.DateField(blank=True, help_text="For subscription/trial software", null=True)),
                ("notes", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Software",
                "verbose_name_plural": "Software",
                "ordering": ["software_name"],
            },
        ),
        migrations.AddField(
            model_name="computerasset",
            name="software",
            field=models.ManyToManyField(blank=True, related_name="computers", to="assets.software"),
        ),
        migrations.AddConstraint(
            model_name="software",
            constraint=models.UniqueConstraint(
                fields=("software_name", "version", "publisher"),
                name="assets_sw_catalog_uniq",
            ),
        ),
        migrations.RunPython(
            migrate_installed_software_to_catalog,
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(
            name="InstalledSoftware",
        ),
    ]
