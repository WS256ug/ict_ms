from assets.models import Asset


def asset_stats(request):
    """
    Add asset statistics to all templates
    """
    if request.user.is_authenticated:
        return {
            "asset_count": Asset.objects.count(),
            "available_asset_count": Asset.objects.filter(status=Asset.STATUS_AVAILABLE).count(),
            "maintenance_asset_count": Asset.objects.filter(status=Asset.STATUS_MAINTENANCE).count(),
            # Backward-compatible keys for templates that still read the old names.
            "active_asset_count": Asset.objects.filter(status=Asset.STATUS_AVAILABLE).count(),
            "faulty_asset_count": Asset.objects.filter(status=Asset.STATUS_MAINTENANCE).count(),
        }
    return {}
