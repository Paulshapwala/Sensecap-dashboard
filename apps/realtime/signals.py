from django.dispatch import receiver
from apps.weather.signals import reading_saved
import redis
import json

import os

REDIS_URL = os.getenv('REDIS_URL')  

if REDIS_URL:
    # Managed Railway Redis config
    redis_client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_keepalive=True,
        socket_timeout=5.0,           # Prevents hanging connections
        socket_connect_timeout=5.0,   # Fast failure if host is unreachable
        retry_on_timeout=True,
        protocol=2,
    )
else:
    # Local development fallback
    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True,
    )

def serialize_reading(instance):
    """Convert WeatherReading instance to JSON"""
    data = {}
    fields = [
        'received_at', 'device_id', 'temperature', 'humidity', 'pressure',
        'wind_speed', 'wind_direction', 'rainfall', 'light_intensity',
        'battery', 'rssi', 'snr'
    ]
    
    for field_name in fields:
        value = getattr(instance, field_name, None)
        if field_name == 'received_at':
            data['time'] = value.isoformat()
        elif value is not None:
            data[field_name] = value
    
    return json.dumps(data)


@receiver(reading_saved)
def on_reading_saved(sender, instance, **kwargs):
    """
    When a reading is saved, publish to Redis.
    ALL workers listen to Redis and broadcast to their local clients.
    """
    json_data = serialize_reading(instance)
    
    try:
        redis_client.publish('weather_updates', json_data)
        print(f"[SIGNAL] Published to Redis: {instance.device_id} @ {instance.received_at}")
    except Exception as e:
        print(f"[SIGNAL] ERROR publishing to Redis: {e}")