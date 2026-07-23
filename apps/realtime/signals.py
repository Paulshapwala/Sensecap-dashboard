from django.dispatch import receiver
from apps.weather.signals import reading_saved
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

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