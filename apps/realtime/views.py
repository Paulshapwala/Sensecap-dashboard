# apps/realtime/views.py
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from apps.weather.services import get_latest_reading
import uuid
import queue
import time
import json

from .registry import registry
from .signals import serialize_reading

@login_required
def stream(request):
    """
    GET /stream/ — SSE endpoint
    1. Send latest reading immediately on connect
    2. Keep connection open for new readings
    """
    client_id = str(uuid.uuid4())
    client_queue = registry.register(client_id)
    
    def event_generator():
        """Generator yields SSE-formatted messages"""
        
        # 1. Send latest reading immediately
        latest = get_latest_reading()
        if latest:
            json_data = serialize_reading(latest)
            yield f'event: new_reading\ndata: {json_data}\n\n'
        
        # 2. Now listen for incoming readings
        last_heartbeat = time.time()
        
        try:
            while True:
                now = time.time()
                
                # Heartbeat every 30 seconds
                if now - last_heartbeat > 30:
                    yield ': keep-alive\n\n'
                    last_heartbeat = now
                
                # Wait for new reading
                try:
                    json_msg = client_queue.get(timeout=5)
                    yield f'event: new_reading\ndata: {json_msg}\n\n'
                except queue.Empty:
                    continue
        
        except GeneratorExit:
            registry.remove(client_id)
            raise
    
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response