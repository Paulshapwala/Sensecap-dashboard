import queue
import threading
from typing import Dict
import redis
import json
import os


# Use REDIS_HOST from environment when running in Docker.
# Inside Docker, services talk to each other by service name (e.g. "redis"),
# not "localhost". When running locally, it falls back to localhost.

REDIS_URL = os.environ.get("REDIS_URL")

if REDIS_URL:
    redis_client = redis.from_url(REDIS_URL)
else:
    redis_client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", 6379)),
        db=0,
    )

class ClientRegistry:
    """
    Thread-safe registry of all connected SSE clients.
    Now with Redis listener for multi-worker broadcasting.
    """
    
    def __init__(self):
        self.clients: Dict[str, queue.Queue] = {}
        self.lock = threading.Lock()
        self._start_redis_listener()
    
    def _start_redis_listener(self):
        """Background thread listens to Redis for broadcasts from other workers"""
        def listen():
            pubsub = redis_client.pubsub()
            pubsub.subscribe('weather_updates')
            
            print("[REGISTRY] Redis listener started")
            for message in pubsub.listen():
                if message['type'] == 'message':
                    json_data = message['data'].decode()
                    # Broadcast to all clients in THIS worker
                    self._broadcast_local(json_data)
        
        thread = threading.Thread(target=listen, daemon=True)
        thread.start()
    
    def register(self, client_id: str) -> queue.Queue:
        """Register a new client"""
        with self.lock:
            q = queue.Queue()
            self.clients[client_id] = q
            print(f"[REGISTRY] Client registered: {client_id} (total: {len(self.clients)})")
            return q
    
    def remove(self, client_id: str) -> None:
        """Remove a client"""
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
                print(f"[REGISTRY] Client removed: {client_id} (total: {len(self.clients)})")
    
    def _broadcast_local(self, json_data: str) -> None:
        """Broadcast to all clients in THIS worker only"""
        with self.lock:
            count = len(self.clients)
            if count == 0:
                return
            
            for client_id, q in self.clients.items():
                try:
                    q.put_nowait(json_data)
                except queue.Full:
                    print(f"[REGISTRY] Queue full for {client_id}, dropping message")
            
            print(f"[REGISTRY] Broadcast to {count} local client(s)")


# Singleton instance — same as before
registry = ClientRegistry()