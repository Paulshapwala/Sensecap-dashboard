"""
Management command: python manage.py run_mqtt_client

Starts the persistent MQTT client that connects to The Things Network,
listens for device uplink messages, and routes them through the ingestion pipeline.

This command runs forever (blocking). Railway runs it as a separate worker process.
"""

import logging
from django.core.management.base import BaseCommand

from apps.mqtt_client.services import start_mqtt_client

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the MQTT client listener for TTN uplink messages"
    
    def handle(self, *args, **options):
        """Entry point for the management command."""
        self.stdout.write(self.style.SUCCESS("Starting MQTT client..."))
        
        try:
            # This blocks forever, listening for MQTT messages
            start_mqtt_client()
        
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nMQTT client stopped by user"))
        
        except RuntimeError as e:
            # Configuration error (missing env vars)
            self.stdout.write(self.style.ERROR(f"Configuration error: {e}"))
            raise
        
        except ConnectionError as e:
            # Cannot reach broker
            self.stdout.write(self.style.ERROR(f"Connection error: {e}"))
            raise
        
        except Exception as e:
            # Unexpected error
            self.stdout.write(self.style.ERROR(f"MQTT client error: {e}"))
            logger.exception("MQTT client failed")
            raise