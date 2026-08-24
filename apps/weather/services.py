"""
weather — Data Layer (spec 4.1)

Owner of the WeatherReading model and all database read/write
operations. This is the ONLY app permitted to touch the WeatherReading
table. Every function below is this app's complete public contract —
other apps must call these, never the ORM directly (Golden Rule, spec 2).

This app has no views, no templates, no URLs.

Public functions (the exposed contract — spec 4.1 "Exposes"):
    save_reading, get_latest_reading, get_readings, get_aggregates,
    get_device_status

Private helpers (internal only, not part of the contract):
    _validate_reading_data
"""

from datetime import datetime

from django.core.exceptions import ValidationError
from django.db.models import Avg, Sum
from django.db.models.functions import TruncHour, TruncDay
from django.utils import timezone

from .models import WeatherReading
from .signals import reading_saved

REQUIRED_FIELDS = [
    "temperature", "humidity", "pressure", "wind_speed", "wind_direction",
    "rainfall", "light_intensity", "rssi", "snr",
    "received_at", "device_id",
]

FIELD_RANGES = {
    "temperature": (-40.0, 85.0),
    "humidity": (0.0, 100.0),
    "pressure": (300.0, 1100.0),
    "wind_speed": (0.0, 60.0),
    "wind_direction": (0.0, 360.0),
    "rainfall": (0.0, 9999.0),
    "light_intensity": (0.0, 120000.0),
    "battery": (0.0, 100.0),
    "rssi": (-150, 0),
    "snr": (-80.0, 80.0),
}


# ── Private helpers ──────────────────────────────────────────────────
# Not part of the exposed contract. Other apps must never import these
# directly — they exist only to support the public functions below.

def _validate_reading_data(data: dict) -> None:
    """Raises ValidationError if required fields are missing or out of range."""
    missing = [f for f in REQUIRED_FIELDS if f not in data or data[f] is None]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")

    for field, (lo, hi) in FIELD_RANGES.items():
        value = data.get(field)
        if value is None:
            continue  # optional field not provided — skip range check
        if not (lo <= value <= hi):
            raise ValidationError(f"{field}={value} is out of range [{lo}, {hi}]")


# ── Public contract (spec 4.1 "Exposes") ─────────────────────────────

def save_reading(data: dict) -> WeatherReading:
    _validate_reading_data(data)

    reading = WeatherReading.objects.create(
        device_id=data["device_id"],
        received_at=data["received_at"],
        temperature=data["temperature"],
        humidity=data["humidity"],
        pressure=data["pressure"],
        wind_speed=data["wind_speed"],
        wind_direction=data["wind_direction"],
        rainfall=data["rainfall"],
        light_intensity=data["light_intensity"],
        battery=data.get("battery"),
        rssi=data["rssi"],
        snr=data["snr"],
        raw_payload=data.get("raw_payload"),
    )

    reading_saved.send(sender=WeatherReading, instance=reading) # signal to notify listeners that a new reading has been saved
    return reading


def get_latest_reading():
    """Returns the most recent WeatherReading, or None if none exist."""
    return WeatherReading.objects.order_by("-received_at").first()


def get_readings(start: datetime, end: datetime):
    """Returns an ordered queryset of WeatherReading between start/end inclusive."""
    return WeatherReading.objects.filter(
        received_at__gte=start, received_at__lte=end
    ).order_by("received_at")


def get_aggregates(start: datetime, end: datetime, period: str):
    """
    period: "hourly" or "daily".
    Returns a list of dicts using database-level aggregation only.
    """
    if period not in ("hourly", "daily"):
        raise ValidationError('period must be "hourly" or "daily"')

    trunc = TruncHour if period == "hourly" else TruncDay

    queryset = (
        WeatherReading.objects.filter(received_at__gte=start, received_at__lte=end)
        .annotate(period_start=trunc("received_at"))
        .values("period_start")
        .annotate(
            avg_temperature=Avg("temperature"),
            avg_humidity=Avg("humidity"),
            avg_pressure=Avg("pressure"),
            avg_wind_speed=Avg("wind_speed"),
            total_rainfall=Sum("rainfall"),
            avg_light_intensity=Avg("light_intensity"),
        )
        .order_by("period_start")
    )
    return list(queryset)


def get_device_status():
    """
    Returns a dict: device_id, last_seen, battery, rssi, snr, status.
    status is "online" if last_seen is within 20 minutes, else "offline".
    """
    latest = get_latest_reading()
    if latest is None:
        return None

    is_online = (timezone.now() - latest.received_at).total_seconds() <= 20 * 60

    return {
        "device_id": latest.device_id,
        "last_seen": latest.received_at,
        "battery": latest.battery,
        "rssi": latest.rssi,
        "snr": latest.snr,
        "status": "online" if is_online else "offline",
    }