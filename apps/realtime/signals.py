# apps/realtime/signals.py
from django.dispatch import receiver
from apps.weather.signals import reading_saved
from .registry import registry
import json

def serialize_reading(instance):
    """
    Convert WeatherReading instance to JSON for SSE broadcast.
    Dynamically extracts fields from the model.
    Skips None values (battery is optional).
    """
    data = {}
    
    # Fields to include (in order)
    fields = [
        'received_at', 'device_id', 'temperature', 'humidity', 'pressure',
        'wind_speed', 'wind_direction', 'rainfall', 'light_intensity',
        'battery', 'rssi', 'snr'
    ]
    
    for field_name in fields:
        value = getattr(instance, field_name, None)
        
        # Special handling for datetime field
        if field_name == 'received_at':
            data['time'] = value.isoformat()
        # Skip None values (battery is optional)
        elif value is not None:
            data[field_name] = value
    
    return json.dumps(data)


@receiver(reading_saved)
def on_reading_saved(sender, instance, **kwargs):
    """
    Signal handler: when weather app fires reading_saved,
    serialize and broadcast to all connected SSE clients.
    """
    json_data = serialize_reading(instance)
    registry.broadcast(json_data)
    print(f"[SIGNAL] Broadcasted: {instance.device_id} @ {instance.received_at}")