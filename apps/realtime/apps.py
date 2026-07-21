# apps/realtime/apps.py
from django.apps import AppConfig

class RealtimeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.realtime'
    
    def ready(self):
        # Import signal handlers to register them
        import apps.realtime.signals