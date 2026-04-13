import logging
import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import SMSNotificationLog


logger = logging.getLogger(__name__)

NON_DIGIT_RE = re.compile(r"\D+")


@dataclass
class SMSResult:
    ok: bool
    status: str
    response_text: str = ""
    provider_message_id: str = ""
    error_message: str = ""


def normalize_phone_number(raw_number):
    if not raw_number:
        return ""

    candidate = str(raw_number).strip()
    if not candidate:
        return ""

    default_country_code = str(
        getattr(settings, "EASY_SEND_SMS_DEFAULT_COUNTRY_CODE", "") or ""
    ).strip().lstrip("+")

    if candidate.startswith("+"):
        candidate = candidate[1:]
    elif candidate.startswith("00"):
        candidate = candidate[2:]
    elif default_country_code and candidate.startswith("0"):
        candidate = f"{default_country_code}{candidate[1:]}"

    return NON_DIGIT_RE.sub("", candidate)


def _message_type(message):
    return "0" if message.isascii() else "1"


def _extract_provider_message_id(response_data):
    message_ids = response_data.get("messageIds") or []
    if not message_ids:
        return ""
    return str(message_ids[0]).strip()


def _send_sms_request(payload):
    encoded_payload = json.dumps(payload).encode("utf-8")
    request = Request(
        getattr(
            settings,
            "EASY_SEND_SMS_BASE_URL",
            "https://restapi.easysendsms.app/v1/rest/sms/send",
        ),
        data=encoded_payload,
        headers={
            "apikey": getattr(settings, "EASY_SEND_SMS_API_KEY", ""),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urlopen(request, timeout=getattr(settings, "EASY_SEND_SMS_TIMEOUT", 15)) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def send_sms_to_number(phone_number, message, *, event_type, recipient=None, related_object=None):
    normalized_number = normalize_phone_number(phone_number)

    if not normalized_number:
        result = SMSResult(
            ok=False,
            status=SMSNotificationLog.STATUS_SKIPPED,
            error_message="Recipient phone number is missing or invalid.",
        )
        _record_sms_result(
            event_type=event_type,
            recipient=recipient,
            related_object=related_object,
            phone_number=normalized_number or "",
            message=message,
            result=result,
        )
        return result

    if not getattr(settings, "EASY_SEND_SMS_ENABLED", False):
        result = SMSResult(
            ok=False,
            status=SMSNotificationLog.STATUS_SKIPPED,
            error_message="Easy Send SMS integration is disabled.",
        )
        _record_sms_result(
            event_type=event_type,
            recipient=recipient,
            related_object=related_object,
            phone_number=normalized_number,
            message=message,
            result=result,
        )
        return result

    api_key = getattr(settings, "EASY_SEND_SMS_API_KEY", "")
    sender_id = getattr(settings, "EASY_SEND_SMS_SENDER_ID", "")
    missing_settings = [
        name
        for name, value in (
            ("EASY_SEND_SMS_API_KEY", api_key),
            ("EASY_SEND_SMS_SENDER_ID", sender_id),
        )
        if not value
    ]
    if missing_settings:
        result = SMSResult(
            ok=False,
            status=SMSNotificationLog.STATUS_FAILED,
            error_message=f"Missing SMS settings: {', '.join(missing_settings)}",
        )
        _record_sms_result(
            event_type=event_type,
            recipient=recipient,
            related_object=related_object,
            phone_number=normalized_number,
            message=message,
            result=result,
        )
        return result

    payload = {
        "from": sender_id,
        "to": normalized_number,
        "text": message,
        "type": _message_type(message),
    }

    try:
        response_data = _send_sms_request(payload)
        response_text = json.dumps(response_data)
        if response_data.get("status"):
            result = SMSResult(
                ok=True,
                status=SMSNotificationLog.STATUS_SENT,
                response_text=response_text,
                provider_message_id=_extract_provider_message_id(response_data),
            )
        else:
            result = SMSResult(
                ok=False,
                status=SMSNotificationLog.STATUS_FAILED,
                response_text=response_text,
                error_message=(
                    response_data.get("description")
                    or response_data.get("error")
                    or "Easy Send SMS returned an unsuccessful response."
                ),
            )
    except HTTPError as exc:
        try:
            error_response = exc.read().decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover - defensive fallback
            error_response = ""
        result = SMSResult(
            ok=False,
            status=SMSNotificationLog.STATUS_FAILED,
            response_text=error_response,
            error_message=f"HTTP {exc.code}: {exc.reason}",
        )
    except URLError as exc:
        result = SMSResult(
            ok=False,
            status=SMSNotificationLog.STATUS_FAILED,
            error_message=f"Connection error: {exc.reason}",
        )
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("Unexpected SMS delivery failure")
        result = SMSResult(
            ok=False,
            status=SMSNotificationLog.STATUS_FAILED,
            error_message=str(exc),
        )

    _record_sms_result(
        event_type=event_type,
        recipient=recipient,
        related_object=related_object,
        phone_number=normalized_number,
        message=message,
        result=result,
    )
    return result


def send_sms_to_user(user, message, *, event_type, related_object=None):
    phone_number = getattr(user, "phone_number", "") if user is not None else ""
    return send_sms_to_number(
        phone_number,
        message,
        event_type=event_type,
        recipient=user,
        related_object=related_object,
    )


def sms_already_sent(event_type, related_object, phone_number, *, notification_date=None):
    normalized_number = normalize_phone_number(phone_number)
    if not related_object or not normalized_number:
        return False

    content_type = ContentType.objects.get_for_model(
        related_object,
        for_concrete_model=False,
    )
    return SMSNotificationLog.objects.filter(
        event_type=event_type,
        content_type=content_type,
        object_id=related_object.pk,
        phone_number=normalized_number,
        notification_date=notification_date or timezone.localdate(),
        status=SMSNotificationLog.STATUS_SENT,
    ).exists()


def _record_sms_result(*, event_type, recipient, related_object, phone_number, message, result):
    content_type = None
    object_id = None
    if related_object is not None and getattr(related_object, "pk", None):
        content_type = ContentType.objects.get_for_model(
            related_object,
            for_concrete_model=False,
        )
        object_id = related_object.pk

    SMSNotificationLog.objects.create(
        event_type=event_type,
        content_type=content_type,
        object_id=object_id,
        recipient=recipient,
        phone_number=phone_number,
        message=message,
        status=result.status,
        provider_message_id=result.provider_message_id,
        provider_response=result.response_text,
        error_message=result.error_message,
        notification_date=timezone.localdate(),
    )
