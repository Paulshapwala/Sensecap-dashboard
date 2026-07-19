"""
mqtt_client/services.py

MQTT client for The Things Network uplink messages.
Connects to TTN broker, receives device data, passes through ingestion,
saves to weather database, and manages retry queue for failures.

No public functions exposed to other apps (except start_mqtt_client for management command).
All other functions are internal to this worker process.

Data flow:
    MQTT message
    ↓
    _on_message() callback
    ↓
    _process_message(raw_payload, received_at)
    ↓
    ingestion.process_payload() → cleaned dict
    ↓
    weather.save_reading() → save to database
    ↓
    On ParseError/other error → _store_failure() → retry queue
"""

import json
import logging
import ssl
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from django.conf import settings
from django.utils import timezone

from apps.ingestion.services import process_payload
from apps.weather.services import save_reading

from .models import RetryQueue

logger = logging.getLogger(__name__)


# ============================================================================
# ENTRY POINT
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
    logger.info("🚀 Starting MQTT client...")
    
    # Validate environment variables
    try:
        app_id = settings.TTN_APP_ID
        api_key = settings.TTN_API_KEY
        device_id = settings.TTN_DEVICE_ID
        broker = settings.TTN_BROKER or "eu1.cloud.thethings.network"
        port = settings.TTN_PORT or 8883
    except AttributeError as e:
        raise RuntimeError(f"Missing required TTN environment variable: {e}")
    
    logger.info(f"📋 Configuration: app_id={app_id}, device_id={device_id}, broker={broker}:{port}")
    
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
        logger.info(f"🔗 Connecting to {broker}:{port}...")
        client.connect(broker, port, keepalive=60)
        
        # Blocking loop - reconnects automatically
        logger.info("⏳ Listening for messages... (press Ctrl+C to stop)")
        client.loop_forever()
    except Exception as e:
        logger.error(f"❌ MQTT client error: {e}")
        raise


# ============================================================================
# MQTT CALLBACKS
# ============================================================================

def _on_connect(client, userdata, flags, rc):
    """MQTT on_connect callback."""
    if rc == 0:
        logger.info("✅ Successfully connected to TTN MQTT broker")
        
        # Subscribe to device topic
        _subscribe_to_topic(client)
        
        # Process any pending retry queue messages
        stats = _retry_pending_messages()
        if stats['processed'] > 0:
            logger.info(
                f"📋 Processed {stats['processed']} messages from retry queue: "
                f"{stats['successful']} successful, {stats['failed']} failed"
            )
    else:
        logger.error(f"❌ MQTT connection failed with code {rc}")


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
        _process_message(raw_payload, received_at)
    
    except Exception as e:
        logger.error(f"❌ Error in MQTT message handler: {e}")


# ============================================================================
# MESSAGE PROCESSING - CORE DATA FLOW
# ============================================================================

def _process_message(raw_payload: str, received_at: datetime):
    """
    Process a single message received from MQTT broker.
    
    Complete flow:
    1. Call ingestion.process_payload() → cleaned dict
    2. Call weather.save_reading() → save to database
    3. On error → store in RetryQueue for retry
    
    Args:
        raw_payload: Raw JSON string from TTN
        received_at: UTC datetime of receipt
    """
    try:
        # Step 1: Parse raw TTN payload via ingestion contract
        cleaned_data = process_payload(raw_payload, received_at)
        device_id = cleaned_data.get('device_id', 'unknown')
        temperature = cleaned_data.get('temperature', 'N/A')
        
        logger.debug(f"Parsed message from device {device_id}")
        
        # Step 2: Save to weather database via weather contract
        reading = save_reading(cleaned_data)
        logger.info(
            f"📡 Sensor data received: device={device_id} | "
            f"temp={temperature}°C | saved to database ✅"
        )
        
        # Data is now in the system - realtime will pick up via signal
    
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"⚠️  Failed to process message: {error_msg}")
        
        # Store for retry
        _store_failure(raw_payload, received_at, error_msg)


# ============================================================================
# RETRY QUEUE MANAGEMENT
# ============================================================================

def _retry_pending_messages():
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
            result = _attempt_retry(entry)
            
            if result["success"]:
                entry.mark_success()
                stats["successful"] += 1
                logger.info(f"Retry {entry.pk}: success on attempt {entry.attempts}")
            else:
                entry.record_attempt(result["error"])
                stats["failed"] += 1
                logger.warning(
                    f"Retry {entry.pk}: failed attempt {entry.attempts}, "
                    f"error: {result['error']}"
                )
        
        except Exception as e:
            logger.error(f"Unexpected error retrying {entry.pk}: {e}")
            entry.record_attempt(f"Unexpected error: {str(e)}")
            stats["failed"] += 1
        
        stats["processed"] += 1
    
    logger.info(
        f"Retry queue complete: {stats['processed']} processed, "
        f"{stats['successful']} successful, {stats['failed']} failed"
    )
    
    return stats


def _attempt_retry(entry: RetryQueue) -> dict:
    """
    Attempt to process a retry queue entry.
    
    Same flow as _process_message: ingestion → weather.save_reading()
    
    Args:
        entry: RetryQueue instance
    
    Returns:
        dict: {"success": bool, "error": str or None}
    """
    try:
        raw_payload = entry.raw_payload
        received_at = entry.received_at
        
        # Parse via ingestion
        cleaned_data = process_payload(raw_payload, received_at)
        
        # Save via weather
        reading = save_reading(cleaned_data)
        
        logger.debug(f"Retry {entry.pk}: success")
        return {"success": True, "error": None}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def _store_failure(raw_payload: str, received_at: datetime, error_message: str):
    """
    Store a failed message in the retry queue.
    
    Args:
        raw_payload: Original TTN JSON string
        received_at: UTC datetime of receipt
        error_message: Error message from processing attempt
    """
    try:
        entry = RetryQueue.objects.create(
            raw_payload=raw_payload,
            received_at=received_at,
            status='pending',
            attempts=0,
            error_message=error_message
        )
        logger.warning(f"📋 Message queued for retry: {entry.pk} | Error: {error_message}")
    
    except Exception as e:
        logger.error(f"❌ Failed to store message in retry queue: {e}")


# ============================================================================
# MQTT CONNECTION HELPERS
# ============================================================================

def _subscribe_to_topic(client):
    """Subscribe to TTN device uplink topic."""
    try:
        app_id = settings.TTN_APP_ID
        device_id = settings.TTN_DEVICE_ID
        
        topic = f"v3/{app_id}@ttn/devices/{device_id}/up"
        client.subscribe(topic, qos=1)
        
        logger.info(f"🔔 Subscribed to topic: {topic}")
    
    except Exception as e:
        logger.error(f"❌ Failed to subscribe to topic: {e}")
        raise