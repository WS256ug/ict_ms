from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Asset, AssetAssignment, MaintenanceRecord


def refresh_asset_status(asset):
    has_open_maintenance = asset.maintenance_records.filter(
        status__in=["open", "in_progress"]
    ).exists()

    has_active_assignment = asset.assignments.filter(
        returned_date__isnull=True
    ).exists()

    if has_open_maintenance:
        new_status = Asset.STATUS_MAINTENANCE
    elif has_active_assignment:
        new_status = Asset.STATUS_ASSIGNED
    else:
        new_status = Asset.STATUS_AVAILABLE

    if asset.status != new_status:
        asset.status = new_status
        asset.save(update_fields=["status", "updated_at"])


@receiver(post_save, sender=MaintenanceRecord)
@receiver(post_delete, sender=MaintenanceRecord)
def maintenance_status_handler(sender, instance, **kwargs):
    refresh_asset_status(instance.asset)


@receiver(post_save, sender=AssetAssignment)
@receiver(post_delete, sender=AssetAssignment)
def assignment_status_handler(sender, instance, **kwargs):
    refresh_asset_status(instance.asset)