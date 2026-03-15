from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from assets.models import Asset

from .models import MaintenanceLog, MaintenanceSchedule


TRACKED_MAINTENANCE_TYPES = {"CORRECTIVE", "PREVENTIVE"}


def _sync_follow_up_schedule(instance):
    if not instance.next_maintenance_date:
        return

    schedule_title = f"{instance.get_maintenance_type_display()} Follow-up"
    MaintenanceSchedule.objects.update_or_create(
        asset=instance.asset,
        title=schedule_title,
        scheduled_date=instance.next_maintenance_date,
        defaults={
            "description": instance.description,
            "assigned_to": instance.performed_by,
            "is_completed": False,
            "completed_at": None,
        },
    )


def _refresh_asset_status(asset):
    has_in_progress_logs = MaintenanceLog.objects.filter(
        asset=asset,
        status="IN_PROGRESS",
        maintenance_type__in=TRACKED_MAINTENANCE_TYPES,
    ).exists()
    has_open_records = asset.maintenance_records.filter(status__in=["open", "in_progress"]).exists()
    has_active_assignment = asset.assignments.filter(returned_date__isnull=True).exists()

    if has_in_progress_logs or has_open_records:
        target_status = Asset.STATUS_MAINTENANCE
    elif has_active_assignment:
        target_status = Asset.STATUS_ASSIGNED
    else:
        target_status = Asset.STATUS_AVAILABLE

    if asset.status != target_status:
        asset.status = target_status
        asset.save(update_fields=["status", "updated_at"])


@receiver(post_save, sender=MaintenanceLog)
def sync_asset_status_and_service_dates(sender, instance, created, **kwargs):
    _sync_follow_up_schedule(instance)
    _refresh_asset_status(instance.asset)


@receiver(post_delete, sender=MaintenanceLog)
def refresh_asset_status_after_log_delete(sender, instance, **kwargs):
    _refresh_asset_status(instance.asset)
