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
    """SSE endpoint for real-time weather updates"""
    client_id = str(uuid.uuid4())
    client_queue = registry.register(client_id)
    
    def event_generator():
        """Generator yields SSE-formatted messages"""
        
        # Send latest reading immediately
        latest = get_latest_reading()
        if latest:
            json_data = serialize_reading(latest)
            # Ensure it's a single line
            if isinstance(json_data, str):
                json_data = json.dumps(json.loads(json_data))
            yield f'event: new_reading\ndata: {json_data}\n\n'
        
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
                    
                    # Ensure JSON is on single line and properly formatted
                    if isinstance(json_msg, str):
                        try:
                            json_msg = json.dumps(json.loads(json_msg))
                        except:
                            continue  # Skip malformed messages
                    
                    yield f'event: new_reading\ndata: {json_msg}\n\n'
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[SSE] Error in stream: {e}")
                    break
        
        except GeneratorExit:
            registry.remove(client_id)
            raise
    
    response = StreamingHttpResponse(
        event_generator(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    response['Connection'] = 'keep-alive'
    return response