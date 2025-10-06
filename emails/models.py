from django.db import models
from django.conf import settings


class EmailAccount(models.Model):
    """Model to store email account configurations"""
    
    PROVIDER_CHOICES = (
        ('gmail', 'Gmail'),
        ('outlook', 'Outlook'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_accounts')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    email_address = models.EmailField()
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'email_accounts'
        unique_together = ('user', 'email_address')
    
    def __str__(self):
        return f'{self.email_address} ({self.provider})'


class Email(models.Model):
    """Model to store email messages"""
    
    IMPORTANCE_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='emails')
    message_id = models.CharField(max_length=255, unique=True, db_index=True)
    thread_id = models.CharField(max_length=255, blank=True, null=True)
    
    sender = models.EmailField()
    recipient = models.EmailField()
    subject = models.TextField(blank=True)
    body = models.TextField(blank=True)
    snippet = models.TextField(blank=True)
    
    importance = models.CharField(max_length=20, choices=IMPORTANCE_CHOICES, default='medium')
    importance_score = models.FloatField(default=0.5)
    importance_analysis = models.TextField(blank=True, null=True)
    
    is_read = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    
    received_at = models.DateTimeField()
    analyzed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'emails'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['-received_at']),
            models.Index(fields=['importance']),
            models.Index(fields=['is_read']),
        ]
    
    def __str__(self):
        return f'{self.subject[:50]} - {self.sender}'

