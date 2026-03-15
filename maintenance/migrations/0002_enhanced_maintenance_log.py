import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F


def populate_completed_at_for_existing_logs(apps, schema_editor):
    MaintenanceLog = apps.get_model("maintenance", "MaintenanceLog")
    MaintenanceLog.objects.filter(status="COMPLETED", completed_at__isnull=True).update(
        completed_at=F("performed_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_enhanced_asset_management"),
        ("maintenance", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="maintenancelog",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="maintenancelog",
            name="status",
            field=models.CharField(
                choices=[
                    ("IN_PROGRESS", "In Progress"),
                    ("COMPLETED", "Completed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="COMPLETED",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="maintenancelog",
            name="performed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="maintenance_performed",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="maintenanceschedule",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="scheduled_maintenance",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="maintenancelog",
            name="status",
            field=models.CharField(
                choices=[
                    ("IN_PROGRESS", "In Progress"),
                    ("COMPLETED", "Completed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="IN_PROGRESS",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="maintenancelog",
            index=models.Index(fields=["status"], name="maintenance_status_f1a23e_idx"),
        ),
        migrations.RunPython(populate_completed_at_for_existing_logs, migrations.RunPython.noop),
    ]
