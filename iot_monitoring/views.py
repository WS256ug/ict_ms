from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import GPSReading, TrackerDevice


def _request_data(request):
    if request.method == "POST":
        return request.POST
    return request.GET


def _parse_decimal(value, field_name):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError({field_name: f"Enter a valid {field_name} value."})


def _parse_float(value, field_name):
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: f"Enter a valid {field_name} value."})


def _parse_int(value, field_name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: f"Enter a valid {field_name} value."})


def _parse_recorded_at(value):
    if not value:
        return timezone.now()

    if str(value).isdigit():
        return timezone.datetime.fromtimestamp(int(value), tz=timezone.utc)

    parsed = parse_datetime(value)
    if parsed is None:
        raise ValidationError({"timestamp": "Enter a valid timestamp."})
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


@csrf_exempt
@require_http_methods(["GET", "POST"])
def gps_ingest(request):
    data = _request_data(request)
    device_id = (data.get("id") or "").strip()
    api_key = (data.get("key") or "").strip()
    latitude_value = data.get("lat")
    longitude_value = data.get("lon")

    missing_fields = [
        field_name
        for field_name, value in (
            ("id", device_id),
            ("key", api_key),
            ("lat", latitude_value),
            ("lon", longitude_value),
        )
        if value in (None, "")
    ]
    if missing_fields:
        return JsonResponse(
            {"status": "error", "errors": {field: "This parameter is required." for field in missing_fields}},
            status=400,
        )

    tracker = (
        TrackerDevice.objects.select_related("asset")
        .filter(device_id=device_id, is_active=True)
        .first()
    )
    if tracker is None:
        return JsonResponse(
            {"status": "error", "errors": {"id": "Unknown or inactive tracker device."}},
            status=404,
        )
    if tracker.api_key != api_key:
        return JsonResponse(
            {"status": "error", "errors": {"key": "Invalid API key."}},
            status=403,
        )

    try:
        reading = GPSReading(
            device=tracker,
            latitude=_parse_decimal(latitude_value, "lat"),
            longitude=_parse_decimal(longitude_value, "lon"),
            accuracy_meters=(
                _parse_float(data.get("accuracy"), "accuracy")
                if data.get("accuracy") not in (None, "")
                else None
            ),
            speed_kmh=(
                _parse_float(data.get("speed"), "speed")
                if data.get("speed") not in (None, "")
                else None
            ),
            battery_level=(
                _parse_int(data.get("battery"), "battery")
                if data.get("battery") not in (None, "")
                else None
            ),
            recorded_at=_parse_recorded_at(data.get("timestamp")),
            raw_payload=request.META.get("QUERY_STRING", ""),
        )
        reading.full_clean()
    except ValidationError as exc:
        return JsonResponse({"status": "error", "errors": exc.message_dict}, status=400)

    reading.save()
    TrackerDevice.objects.filter(pk=tracker.pk).update(last_seen_at=reading.recorded_at)

    return HttpResponse("OK", content_type="text/plain")
