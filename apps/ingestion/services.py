"""
ingestion.services
==================

Core payload parsing service. Transforms raw TTN MQTT JSON from a SenseCAP S2120
weather station into the clean dict shape required by weather.save_reading().

All functions are internal to this app. Exceptions are raised and handled
downstream by callers (mqtt_client, weather).
"""

import json
from datetime import datetime
from typing import Any, Dict

from .exceptions import ParseError


# SenseCAP S2120 measurementId -> field name mapping
_MEASUREMENT_ID_MAP = {
    4097: "temperature",       # Air Temperature
    4098: "humidity",          # Air Humidity
    4099: "light_intensity",   # Light Intensity
    4101: "pressure",          # Barometric Pressure
    4104: "wind_direction",    # Wind Direction Sensor
    4105: "wind_speed",        # Wind Speed
    4113: "rainfall",          # Rain Gauge
    3000: "battery",           # Battery Level (optional)
}

_REQUIRED_MEASUREMENT_FIELDS = frozenset([
    "temperature",
    "humidity",
    "pressure",
    "wind_direction",
    "wind_speed",
    "rainfall",
    "light_intensity",
])

_OPTIONAL_MEASUREMENT_FIELDS = frozenset(["battery"])

# Physically-plausible value ranges
_VALIDATION_RANGES = {
    "temperature": (-40.0, 85.0),
    "humidity": (0.0, 100.0),
    "pressure": (300.0, 1100.0),
    "wind_speed": (0.0, 60.0),
    "wind_direction": (0.0, 360.0),
    "rainfall": (0.0, 9999.0),
    "light_intensity": (0.0, 120000.0),
    "battery": (0.0, 100.0),
    "rssi": (-150, 0),
    "snr": (-20.0, 20.0),
}

# Unit conversions
_PA_TO_HPA = 1 / 100  # Pressure: Pascals to hectopascals


def process_payload(raw_payload: str, received_at: datetime) -> Dict[str, Any]:
    """
    Parse and validate a raw TTN uplink payload from a SenseCAP S2120 sensor.

    Args:
        raw_payload: raw JSON string exactly as received from the MQTT broker.
        received_at: UTC datetime of when the message was received.

    Returns:
        A dict with all fields required by weather.save_reading():
        temperature, humidity, pressure, wind_speed, wind_direction, rainfall,
        light_intensity, battery, rssi, snr, received_at, device_id, raw_payload.

    Raises:
        ParseError: if the payload is malformed, missing required sensor fields,
            or contains physically implausible values.
    """
    envelope = _load_json(raw_payload)
    device_id = _extract_device_id(envelope)
    measurements = _extract_measurements(envelope)
    rssi, snr = _extract_radio_metrics(envelope)

    result: Dict[str, Any] = dict(measurements)
    result["rssi"] = rssi
    result["snr"] = snr
    result["received_at"] = received_at
    result["device_id"] = device_id
    result["raw_payload"] = envelope

    return result


def _load_json(raw_payload: str) -> dict:
    """Load and validate JSON structure."""
    try:
        envelope = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ParseError(f"raw_payload is not valid JSON: {exc}") from exc

    if not isinstance(envelope, dict):
        raise ParseError("raw_payload must decode to a JSON object")

    return envelope


def _extract_device_id(envelope: dict) -> str:
    """Extract and validate device ID from envelope."""
    try:
        device_id = envelope["end_device_ids"]["device_id"]
    except (KeyError, TypeError) as exc:
        raise ParseError(
            "missing required field: end_device_ids.device_id"
        ) from exc

    if not isinstance(device_id, str) or not device_id:
        raise ParseError("end_device_ids.device_id must be a non-empty string")

    return device_id


def _extract_measurements(envelope: dict) -> Dict[str, float]:
    """Extract sensor measurements from nested/flat message arrays."""
    try:
        messages = envelope["uplink_message"]["decoded_payload"]["messages"]
    except (KeyError, TypeError) as exc:
        raise ParseError(
            "missing required field: uplink_message.decoded_payload.messages"
        ) from exc

    if not isinstance(messages, list):
        raise ParseError("uplink_message.decoded_payload.messages must be a list")

    values: Dict[str, float] = {}

    # Flatten messages (may be nested arrays or flat array)
    flat_messages = []
    for item in messages:
        if isinstance(item, list):
            flat_messages.extend(item)
        else:
            flat_messages.append(item)

    for message in flat_messages:
        try:
            measurement_id = int(message["measurementId"])
            raw_value = message["measurementValue"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ParseError(f"malformed measurement entry: {message!r}") from exc

        field_name = _MEASUREMENT_ID_MAP.get(measurement_id)
        if field_name is None:
            # Unknown measurementId — ignore, don't error
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ParseError(
                f"measurementId {measurement_id} ({field_name}) has a "
                f"non-numeric value: {raw_value!r}"
            ) from exc

        # Apply unit conversions
        if field_name == "pressure":
            value = value * _PA_TO_HPA  # Convert Pa to hPa

        _validate_field(field_name, value)
        values[field_name] = value

    missing = _REQUIRED_MEASUREMENT_FIELDS - values.keys()
    if missing:
        raise ParseError(
            f"missing required sensor measurement(s): {sorted(missing)}"
        )

    return values


def _extract_radio_metrics(envelope: dict) -> tuple[int, float]:
    """Extract RSSI and SNR from rx_metadata."""
    try:
        rx_metadata = envelope["uplink_message"]["rx_metadata"][0]
        rssi = int(rx_metadata["rssi"])
        snr = float(rx_metadata["snr"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ParseError(
            "missing or malformed field: uplink_message.rx_metadata[0] (rssi/snr)"
        ) from exc

    _validate_field("rssi", rssi)
    _validate_field("snr", snr)

    return rssi, snr


def _validate_field(field_name: str, value: float) -> None:
    """Raise ParseError if value falls outside field's allowed range."""
    lo, hi = _VALIDATION_RANGES[field_name]
    if not (lo <= value <= hi):
        raise ParseError(
            f"'{field_name}' value {value!r} is outside the valid range "
            f"[{lo}, {hi}]"
        )