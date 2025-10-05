from django.db import models
from django.conf import settings


class WhatsAppMessage(models.Model):
    """Model to store WhatsApp messages sent via Cloud API"""
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='whatsapp_messages')
    to_number = models.CharField(max_length=20)
    message = models.TextField()
    message_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    
    # Alert context
    alert_type = models.CharField(max_length=50, blank=True, null=True)
    related_email_id = models.IntegerField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'whatsapp_messages'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Message to {self.to_number} - {self.status}'


class WhatsAppWebhook(models.Model):
    """Model to log WhatsApp webhook events"""
    
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'whatsapp_webhooks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.event_type} - {self.created_at}'
