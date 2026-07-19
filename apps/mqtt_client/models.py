from django.db import models
from django.utils import timezone


class RetryQueueManager(models.Manager):
    """Custom manager for RetryQueue queries."""
    
    def pending(self):
        """Get all messages pending retry."""
        return self.filter(status='pending')
    
    def failed(self):
        """Get all messages that have permanently failed."""
        return self.filter(status='failed')
    
    def successful(self):
        """Get all messages that have been successfully processed."""
        return self.filter(status='success')
    
    def retryable(self):
        """Get pending messages that haven't hit max attempts (3)."""
        return self.filter(status='pending', attempts__lt=3)


class RetryQueue(models.Model):
    """
    Stores MQTT payloads that failed to process via ingestion.process_payload().
    
    When the mqtt_client receives a message and ingestion raises ParseError,
    the raw payload is stored here for retry. Messages are retried when:
    1. Connection is lost and reconnects (process all pending in received_at order)
    2. Scheduled retry task runs (if implemented later)
    
    Max 3 attempts per message. After that, status='failed' for manual review.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending Retry'),
        ('success', 'Successfully Processed'),
        ('failed', 'Permanently Failed'),
    ]
    
    # Original message data
    raw_payload = models.TextField(
        help_text="Original TTN JSON string exactly as received from MQTT broker"
    )
    received_at = models.DateTimeField(
        help_text="UTC datetime when the message was originally received"
    )
    
    # Retry tracking
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status: pending retry, successfully processed, or permanently failed"
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of processing attempts (max 3)"
    )
    last_attempted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="UTC timestamp of the last retry attempt"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message from the most recent processing attempt"
    )
    
    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this retry queue entry was created"
    )
    
    objects = RetryQueueManager()
    
    class Meta:
        ordering = ['received_at']  # Always process in chronological order
        indexes = [
            models.Index(fields=['status', 'attempts']),
            models.Index(fields=['received_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = "MQTT Retry Queue Entry"
        verbose_name_plural = "MQTT Retry Queue Entries"
    
    def __str__(self):
        return f"RetryQueue {self.pk} | {self.received_at} | {self.status} | attempts={self.attempts}"
    
    def mark_success(self):
        """Mark this message as successfully processed."""
        self.status = 'success'
        self.last_attempted_at = timezone.now()
        self.save(update_fields=['status', 'last_attempted_at'])
    
    def mark_failed(self, error_message=""):
        """Mark this message as permanently failed (max attempts reached)."""
        self.status = 'failed'
        self.error_message = error_message
        self.last_attempted_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'last_attempted_at'])
    
    def record_attempt(self, error_message=""):
        """
        Record a retry attempt. Increments attempt counter.
        If max attempts reached, marks as failed.
        """
        self.attempts += 1
        self.last_attempted_at = timezone.now()
        self.error_message = error_message
        
        if self.attempts >= 3:
            self.status = 'failed'
        
        self.save(update_fields=['attempts', 'last_attempted_at', 'error_message', 'status'])