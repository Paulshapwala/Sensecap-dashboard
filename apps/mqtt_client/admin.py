"""
mqtt_client/admin.py

Django admin interface for RetryQueue model.
Useful for monitoring failed MQTT messages and manual intervention.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import RetryQueue


class RetryQueueAdmin(admin.ModelAdmin):
    """Admin interface for MQTT retry queue."""
    
    list_display = (
        'id',
        'received_at',
        'status_badge',
        'attempts',
        'device_id_from_payload',
        'last_attempted_at',
    )
    
    list_filter = (
        'status',
        'attempts',
        'created_at',
        'received_at',
    )
    
    search_fields = (
        'raw_payload',
        'error_message',
    )
    
    readonly_fields = (
        'raw_payload_formatted',
        'created_at',
        'received_at',
        'last_attempted_at',
        'status',
        'attempts',
        'error_message',
    )
    
    fieldsets = (
        ('Message', {
            'fields': ('received_at', 'raw_payload_formatted'),
            'description': 'Original TTN MQTT message'
        }),
        ('Retry Status', {
            'fields': ('status', 'attempts', 'last_attempted_at', 'error_message'),
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    
    actions = [
        'mark_pending',
        'mark_failed',
    ]
    
    def has_add_permission(self, request):
        """Prevent manual creation - only created by mqtt_client."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion - keep audit trail."""
        return False
    
    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            'pending': '#FFA500',    # Orange
            'success': '#50FA7B',    # Green
            'failed': '#FF5555',     # Red
        }
        color = colors.get(obj.status, '#6272A4')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def device_id_from_payload(self, obj):
        """Extract and display device_id from raw payload."""
        try:
            import json
            data = json.loads(obj.raw_payload)
            device_id = data.get('end_device_ids', {}).get('device_id', '—')
            return device_id
        except:
            return '—'
    device_id_from_payload.short_description = 'Device ID'
    
    def raw_payload_formatted(self, obj):
        """Display raw payload as formatted JSON."""
        try:
            import json
            data = json.loads(obj.raw_payload)
            formatted = json.dumps(data, indent=2)
            return format_html(
                '<pre style="background: #282A36; color: #F8F8F2; '
                'padding: 10px; border-radius: 4px; '
                'max-height: 400px; overflow-y: auto;">{}</pre>',
                formatted
            )
        except:
            return format_html(
                '<pre style="background: #282A36; color: #F8F8F2; '
                'padding: 10px; border-radius: 4px;">{}</pre>',
                obj.raw_payload[:500]
            )
    raw_payload_formatted.short_description = 'Raw TTN Payload'
    
    def mark_pending(self, request, queryset):
        """Action to mark selected entries as pending retry."""
        count = queryset.update(status='pending', attempts=0)
        self.message_user(request, f'{count} entries marked as pending.')
    mark_pending.short_description = 'Mark as pending (retry)'
    
    def mark_failed(self, request, queryset):
        """Action to mark selected entries as permanently failed."""
        count = queryset.update(status='failed')
        self.message_user(request, f'{count} entries marked as failed.')
    mark_failed.short_description = 'Mark as failed (give up)'


admin.site.register(RetryQueue, RetryQueueAdmin)