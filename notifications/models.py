from django.db import models
from django.conf import settings


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
