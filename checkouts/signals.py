from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from notifications.models import Alert, Notification

from .models import CheckoutHistory, CheckoutRequest, GeofenceAlert, GPSLocation


def _status_actor(instance):
    return getattr(instance, "_changed_by", None)


def _notify_users(users, notification_type, title, message):
    seen_user_ids = set()
    notifications = []

    for user in users:
        if user is None or not getattr(user, "pk", None) or user.pk in seen_user_ids:
            continue
        seen_user_ids.add(user.pk)
        notifications.append(
            Notification(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)


@receiver(pre_save, sender=CheckoutRequest)
def stash_previous_checkout_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return

    instance._previous_status = (
        sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )


@receiver(post_save, sender=CheckoutRequest)
def handle_checkout_request_updates(sender, instance, created, **kwargs):
    User = get_user_model()
    asset = instance.asset
    previous_status = getattr(instance, "_previous_status", None)
    status_changed = created or previous_status != instance.status

    if instance.status in ("CHECKED_OUT", "OVERDUE"):
        if asset.assigned_to_id != instance.requested_by_id:
            asset.assigned_to = instance.requested_by
            asset.save(update_fields=["assigned_to"])
    elif instance.status in ("RETURNED", "REJECTED", "CANCELLED"):
        has_other_active_checkout = asset.checkouts.exclude(pk=instance.pk).filter(
            status__in=CheckoutRequest.ACTIVE_STATUSES
        ).exists()
        if asset.assigned_to_id == instance.requested_by_id and not has_other_active_checkout:
            asset.assigned_to = None
            asset.save(update_fields=["assigned_to"])

    if created:
        admins = User.objects.filter(role="ADMIN", is_active=True)
        _notify_users(
            admins,
            "SYSTEM",
            f"New Checkout Request: {instance.request_number}",
            (
                f"{instance.requested_by.get_full_name()} requested {instance.asset.name} "
                f"from {instance.requested_checkout_date} to {instance.requested_return_date}."
            ),
        )
        return

    if not status_changed:
        return

    CheckoutHistory.objects.create(
        checkout=instance,
        previous_status=previous_status or "PENDING",
        new_status=instance.status,
        changed_by=_status_actor(instance),
        changed_at=timezone.now(),
    )

    if instance.status == "APPROVED":
        _notify_users(
            [instance.requested_by],
            "SYSTEM",
            f"Checkout Approved: {instance.request_number}",
            f"Your request for {instance.asset.name} has been approved.",
        )
    elif instance.status == "REJECTED":
        _notify_users(
            [instance.requested_by],
            "SYSTEM",
            f"Checkout Rejected: {instance.request_number}",
            (
                f"Your request for {instance.asset.name} was rejected. "
                f"Reason: {instance.rejection_reason or 'Not specified'}"
            ),
        )
    elif instance.status == "OVERDUE":
        admins = User.objects.filter(role__in=("ADMIN", "TECHNICIAN"), is_active=True)
        overdue_message = f"{instance.asset.name} is overdue by {instance.days_overdue} day(s)."
        _notify_users(
            [instance.requested_by, *admins],
            "ALERT",
            f"Overdue Checkout: {instance.request_number}",
            overdue_message,
        )


@receiver(post_save, sender=GPSLocation)
def check_geofence_events(sender, instance, created, **kwargs):
    if not created:
        return

    checkout = instance.checkout
    asset = checkout.asset
    User = get_user_model()
    admins = list(User.objects.filter(role__in=("ADMIN", "TECHNICIAN"), is_active=True))

    if asset.geofence_enabled:
        active_exit_alert = GeofenceAlert.objects.filter(
            checkout=checkout,
            alert_type="GEOFENCE_EXIT",
            is_resolved=False,
        ).first()

        if not instance.is_inside_geofence and active_exit_alert is None:
            distance = int(instance.distance_from_center_meters or 0)
            message = (
                f"Asset {asset.asset_tag} ({asset.name}) has left the campus geofence. "
                f"Distance from center: {distance} meters."
            )
            geofence_alert = GeofenceAlert.objects.create(
                checkout=checkout,
                gps_location=instance,
                alert_type="GEOFENCE_EXIT",
                message=message,
            )
            Alert.objects.create(
                title=f"Geofence Alert: {asset.asset_tag}",
                message=geofence_alert.message,
                severity="WARNING",
                asset=asset,
            )
            _notify_users(
                [*admins, checkout.requested_by],
                "ALERT",
                f"Asset Left Geofence: {asset.asset_tag}",
                geofence_alert.message,
            )
        elif instance.is_inside_geofence and active_exit_alert is not None:
            active_exit_alert.is_resolved = True
            active_exit_alert.resolution_notes = "Asset returned inside the geofence."
            active_exit_alert.save(update_fields=["is_resolved", "resolution_notes"])
            GeofenceAlert.objects.create(
                checkout=checkout,
                gps_location=instance,
                alert_type="GEOFENCE_ENTRY",
                message=f"Asset {asset.asset_tag} returned inside the geofence.",
                is_resolved=True,
            )

    if instance.battery_level is not None and instance.battery_level < 20:
        existing_low_battery_alert = GeofenceAlert.objects.filter(
            checkout=checkout,
            alert_type="LOW_BATTERY",
            is_resolved=False,
        ).exists()
        if not existing_low_battery_alert:
            message = (
                f"GPS tracker battery low ({instance.battery_level}%) on asset {asset.asset_tag}."
            )
            GeofenceAlert.objects.create(
                checkout=checkout,
                gps_location=instance,
                alert_type="LOW_BATTERY",
                message=message,
            )
            Alert.objects.create(
                title=f"Low GPS Battery: {asset.asset_tag}",
                message=message,
                severity="WARNING",
                asset=asset,
            )
            _notify_users(
                admins,
                "ALERT",
                f"Low GPS Battery: {asset.asset_tag}",
                message,
            )
