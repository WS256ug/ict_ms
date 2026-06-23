from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def check_easy_send_sms_settings(app_configs, **kwargs):
    if not getattr(settings, "EASY_SEND_SMS_ENABLED", False):
        return []

    issues = []
    required_settings = (
        "EASY_SEND_SMS_API_KEY",
        "EASY_SEND_SMS_SENDER_ID",
        "EASY_SEND_SMS_DEFAULT_COUNTRY_CODE",
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

    base_url = getattr(settings, "EASY_SEND_SMS_BASE_URL", "")
    if base_url and urlparse(base_url).scheme != "https":
        issues.append(
            Warning(
                "EASY_SEND_SMS_BASE_URL does not use HTTPS.",
                hint="Use the Easy Send SMS HTTPS endpoint in production.",
                id="notifications.W001",
            )
        )

    return issues
