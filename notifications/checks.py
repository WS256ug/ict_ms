from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def check_ego_sms_settings(app_configs, **kwargs):
    if not getattr(settings, "EGO_SMS_ENABLED", False):
        return []

    issues = []
    required_settings = (
        "EGO_SMS_USERNAME",
        "EGO_SMS_API_KEY",
        "EGO_SMS_SENDER_ID",
        "EGO_SMS_DEFAULT_COUNTRY_CODE",
    )
    missing_settings = [
        name for name in required_settings if not getattr(settings, name, "")
    ]
    if missing_settings:
        issues.append(
            Error(
                f"Missing enabled SMS settings: {', '.join(missing_settings)}.",
                hint="Configure them in the process environment or the project .env file.",
                id="notifications.E001",
            )
        )

    base_url = getattr(settings, "EGO_SMS_BASE_URL", "")
    if base_url and urlparse(base_url).scheme != "https":
        issues.append(
            Warning(
                "EGO_SMS_BASE_URL does not use HTTPS.",
                hint="Use the EgoSMS HTTPS endpoint in production.",
                id="notifications.W001",
            )
        )

    sender_id = getattr(settings, "EGO_SMS_SENDER_ID", "")
    if len(sender_id) > 11:
        issues.append(
            Warning(
                "EGO_SMS_SENDER_ID is longer than 11 characters.",
                hint="Use an approved EgoSMS sender ID with at most 11 characters.",
                id="notifications.W002",
            )
        )

    return issues
