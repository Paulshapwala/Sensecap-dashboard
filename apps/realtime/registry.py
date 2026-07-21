# apps/realtime/registry.py
import queue
import threading
from typing import Dict

class ClientRegistry:
    """
    Thread-safe registry of all connected SSE clients.
    Each client has their own queue. When a reading arrives,
    we broadcast to all queues.
    """
    
    def __init__(self):
        self.clients: Dict[str, queue.Queue] = {}
        self.lock = threading.Lock()
    
    def register(self, client_id: str) -> queue.Queue:
        """
        Register a new client (called when browser connects to /stream/)
        Returns: queue.Queue for this client
        """
        with self.lock:
            q = queue.Queue()
            self.clients[client_id] = q
            print(f"[REGISTRY] Client registered: {client_id} (total: {len(self.clients)})")
            return q
    
    def remove(self, client_id: str) -> None:
        """
        Remove a client (called when browser disconnects)
        """
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
                print(f"[REGISTRY] Client removed: {client_id} (total: {len(self.clients)})")
    
    def broadcast(self, json_data: str) -> None:
        """
        Broadcast a message to all connected clients.
        Called by signal handler when new reading arrives.
        """
        with self.lock:
            count = len(self.clients)
            if count == 0:
                print(f"[REGISTRY] Broadcast: no clients connected")
                return
            
            for client_id, q in self.clients.items():
                try:
                    q.put_nowait(json_data)
                except queue.Full:
                    # Queue is full, client is slow — drop the message
                    print(f"[REGISTRY] Queue full for {client_id}, dropping message")
            
            print(f"[REGISTRY] Broadcast to {count} client(s)")


# Singleton instance — used everywhere in the app
registry = ClientRegistry()