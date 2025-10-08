from django.db import models
from django.conf import settings


from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    """Stores user notification preferences."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notification_preferences'
    )

    # Notification channels
    email_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=False)
    sms_notifications = models.BooleanField(default=False)
    whatsapp_notifications = models.BooleanField(default=True)

    # Summaries
    daily_summary = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notification_preferences'

    def __str__(self):
        return f"Notification Preferences for {self.user.email or self.user.username}"



class Notification(models.Model):
    """Model to store user notifications"""
    
    TYPE_CHOICES = (
        ('email', 'Email Alert'),
        ('payment', 'Payment'),
        ('subscription', 'Subscription'),
        ('system', 'System'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Metadata
    related_object_id = models.IntegerField(blank=True, null=True)
    data = models.JSONField(blank=True, null=True)
    
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read']),
        ]
    
    def __str__(self):
        return f'{self.title} - {self.user.email}'
