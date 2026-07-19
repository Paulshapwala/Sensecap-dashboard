"""
mqtt_client/services.py

Public functions:
  - start_mqtt_client()        → Entry point for management command
  - process_received_message() → Handle incoming MQTT payload
  - retry_pending_messages()   → Process retry queue on reconnect

Private functions (prefix _):
  - _connect_to_broker()       → Establish TLS connection to TTN
  - _subscribe_to_topic()      → Subscribe to device uplink topic
  - _handle_message()          → MQTT on_message callback
  - _calculate_backoff()       → Exponential backoff delay
  - _attempt_process()         → Try ingestion.process_payload()
  - _store_failure()           → Queue message for retry
  - _handle_connection_loss()  → Reconnect logic
"""

import json
import logging
import ssl
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt
from django.conf import settings
from django.utils import timezone

from apps.ingestion.services import process_payload

from .models import RetryQueue

logger = logging.getLogger(__name__)


# ============================================================================
# PUBLIC FUNCTIONS - Called by management command or other apps
# ============================================================================

def start_mqtt_client():
    """
    Entry point for: python manage.py run_mqtt_client
    
    Establishes persistent connection to TTN MQTT broker and runs the event loop.
    This function blocks forever. On connection loss, reconnects with exponential backoff.
    
    Raises:
        RuntimeError: If required environment variables are missing
        ConnectionError: If broker cannot be reached after retries
    """
    logger.info("Starting MQTT client...")
    
    # Validate environment variables
    try:
        app_id = settings.TTN_APP_ID
        api_key = settings.TTN_API_KEY
        device_id = settings.TTN_DEVICE_ID
        broker = settings.TTN_BROKER or "eu1.cloud.thethings.network"
        port = settings.TTN_PORT or 8883
    except AttributeError as e:
        raise RuntimeError(f"Missing required TTN environment variable: {e}")
    
    # Create MQTT client
    client_id = f"weather-dashboard-{int(time.time())}"
    client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
    
    # Attach callbacks
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.on_disconnect = _on_disconnect
    
    # Configure TLS
    try:
        client.tls_set(
            ca_certs=None,  # Use system CA bundle
            certfile=None,
            keyfile=None,
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
            ciphers=None
        )
        client.tls_insecure = False
    except Exception as e:
        logger.error(f"Failed to configure TLS: {e}")
        raise
    
    # Set username and password
    client.username_pw_set(app_id, api_key)
    
    # Connect and loop
    try:
        logger.info(f"Connecting to {broker}:{port} as {app_id}...")
        client.connect(broker, port, keepalive=60)
        
        # Blocking loop - reconnects automatically
        client.loop_forever()
    except Exception as e:
        logger.error(f"MQTT client error: {e}")
        raise


def process_received_message(raw_payload: str, received_at: datetime):
    """
    Process a single message received from MQTT broker.
    
    Flow:
    1. Call ingestion.process_payload(raw_payload, received_at)
    2. On success → return cleaned data
    3. On error → store in RetryQueue for later retry
    
    Args:
        raw_payload: Raw JSON string from TTN
        received_at: UTC datetime of receipt
    
    Returns:
        dict: {"success": bool, "error": str or None, "reading": obj or None}
    """
    logger.debug(f"Processing message received at {received_at}")
    
    try:
        # Parse the raw payload
        cleaned_data = process_payload(raw_payload, received_at)
        
        # Forward to weather app (will be called via weather service)
        # This is where the data actually enters the system
        logger.info(f"Successfully parsed message from device {cleaned_data.get('device_id')}")
        
        return {
            "success": True,
            "error": None,
            "reading": cleaned_data
        }
    
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Error processing message: {error_msg}")
        
        # Store for retry
        _store_failure(raw_payload, received_at, error_msg)
        
        return {
            "success": False,
            "error": error_msg,
            "reading": None
        }


def retry_pending_messages():
    """
    Process all pending messages in the retry queue.
    
    Called on MQTT reconnection. Processes messages in received_at order (FIFO).
    Updates retry queue status after each attempt.
    
    Returns:
        dict: {"processed": int, "successful": int, "failed": int}
    """
    logger.info("Processing retry queue...")
    
    stats = {"processed": 0, "successful": 0, "failed": 0}
    
    # Get all retryable messages (pending, attempts < 3)
    pending = RetryQueue.objects.retryable()
    
    if not pending.exists():
        logger.debug("No pending messages in retry queue")
        return stats
    
    for entry in pending:
        try:
            # Attempt to process
            result = _attempt_process(entry)
            
            if result["success"]:
                entry.mark_success()
                stats["successful"] += 1
                logger.info(f"Retry queue {entry.pk}: success on attempt {entry.attempts}")
            else:
                entry.record_attempt(result["error"])
                stats["failed"] += 1
                logger.warning(
                    f"Retry queue {entry.pk}: failed attempt {entry.attempts}, "
                    f"error: {result['error']}"
                )
        
        except Exception as e:
            logger.error(f"Unexpected error processing retry queue {entry.pk}: {e}")
            entry.record_attempt(f"Unexpected error: {str(e)}")
            stats["failed"] += 1
        
        stats["processed"] += 1
    
    logger.info(
        f"Retry queue complete: {stats['processed']} processed, "
        f"{stats['successful']} successful, {stats['failed']} failed"
    )
    
    return stats


# ============================================================================
# PRIVATE FUNCTIONS - Internal use only
# ============================================================================

def _on_connect(client, userdata, flags, rc):
    """MQTT on_connect callback."""
    if rc == 0:
        logger.info("MQTT broker connected successfully")
        
        # Subscribe to device topic
        _subscribe_to_topic(client)
        
        # Process any pending retry queue messages
        retry_pending_messages()
    else:
        logger.error(f"MQTT connection failed with code {rc}")


def _on_disconnect(client, userdata, rc):
    """MQTT on_disconnect callback."""
    if rc == 0:
        logger.info("MQTT disconnect (clean)")
    else:
        logger.warning(f"MQTT unexpected disconnect with code {rc}. Reconnecting...")


def _on_message(client, userdata, msg):
    """MQTT on_message callback - invoked for each received message."""
    try:
        raw_payload = msg.payload.decode('utf-8')
        received_at = timezone.now()
        
        logger.debug(f"Received MQTT message on topic {msg.topic}")
        
        # Process the message
        process_received_message(raw_payload, received_at)
    
    except Exception as e:
        logger.error(f"Error in MQTT message handler: {e}")


def _subscribe_to_topic(client):
    """Subscribe to TTN device uplink topic."""
    try:
        app_id = settings.TTN_APP_ID
        device_id = settings.TTN_DEVICE_ID
        
        topic = f"v3/{app_id}@ttn/devices/{device_id}/up"
        client.subscribe(topic, qos=1)
        
        logger.info(f"Subscribed to topic: {topic}")
    
    except Exception as e:
        logger.error(f"Failed to subscribe to topic: {e}")
        raise


def _calculate_backoff(attempt: int) -> int:
    """
    Calculate exponential backoff delay.
    
    Sequence: 1s → 2s → 4s → 8s → 16s → 32s → max 60s
    
    Args:
        attempt: Attempt number (0-indexed)
    
    Returns:
        Delay in seconds
    """
    delay = min(2 ** attempt, 60)
    return int(delay)


def _attempt_process(retry_queue_entry: RetryQueue) -> dict:
    """
    Attempt to process a retry queue entry.
    
    Args:
        retry_queue_entry: RetryQueue instance
    
    Returns:
        dict: {"success": bool, "error": str or None}
    """
    try:
        raw_payload = retry_queue_entry.raw_payload
        received_at = retry_queue_entry.received_at
        
        # Try to parse via ingestion
        cleaned_data = process_payload(raw_payload, received_at)
        
        logger.debug(f"Retry queue {retry_queue_entry.pk}: parsed successfully")
        return {"success": True, "error": None}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def _store_failure(raw_payload: str, received_at: datetime, error_message: str):
    """
    Store a failed message in the retry queue.
    
    Args:
        raw_payload: Original TTN JSON string
        received_at: UTC datetime of receipt
        error_message: Error message from parsing attempt
    """
    try:
        entry = RetryQueue.objects.create(
            raw_payload=raw_payload,
            received_at=received_at,
            status='pending',
            attempts=0,
            error_message=error_message
        )
        logger.info(f"Stored message in retry queue: {entry.pk}")
    
    except Exception as e:
        logger.error(f"Failed to store message in retry queue: {e}")