"""
ingestion — Payload Parser

Transforms raw TTN MQTT JSON into a clean validated dictionary matching
weather.save_reading()'s expected shape. Contains all knowledge of the
TTN envelope format and SenseCAP S2120 field names.

No models, no views, no URLs, no side effects.

Public contract:
    process_payload(raw_payload, received_at) -> dict
    ParseError
"""

from .exceptions import ParseError  # noqa: E402
from .services import process_payload  # noqa: E402

__all__ = ["process_payload", "ParseError"]