"""
Management command: python manage.py run_mqtt_client

Runs the MQTT client worker. This command blocks forever, listening for
messages from The Things Network, processing them through ingestion,
and persisting to the weather database.

Usage:
  python manage.py run_mqtt_client           # Local development
  
Railway runs this as a background worker process via Procfile:
  worker: python manage.py run_mqtt_client
"""

import logging
from django.core.management.base import BaseCommand

from apps.mqtt_client.services import start_mqtt_client

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run MQTT client to listen for TTN uplink messages"
    
    def handle(self, *args, **options):
        """Start the MQTT client (blocks forever)."""
        self.stdout.write(self.style.SUCCESS("Starting MQTT client worker..."))
        
        try:
            start_mqtt_client()
        
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nMQTT client stopped"))
        
        except RuntimeError as e:
            self.stdout.write(self.style.ERROR(f"Configuration error: {e}"))
            raise
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"MQTT client error: {e}"))
            logger.exception("MQTT client failed")
            raise