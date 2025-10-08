from django.db import models
from django.conf import settings

# assistant/models.py
class AssistantMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assistant_messages')
    role = models.CharField(max_length=20, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']



class AssistantConfig(models.Model):
    """Model to store AI assistant configurations"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assistant_configs')
    is_enabled = models.BooleanField(default=False)
    default_model = models.CharField(max_length=100, default='gpt-4')
    max_response_length = models.IntegerField(default=500)
    temperature = models.FloatField(default=0.7)
    top_p = models.FloatField(default=1.0)
    tone = models.CharField(max_length=50, default='professional')
    custom_instructions = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'assistant_configs'
        unique_together = ('user',)
    
    def __str__(self):
        return f'AssistantConfig for {self.user.email}'


class AssistantTask(models.Model):
    """Model to store AI assistant tasks"""
    
    TASK_TYPE_CHOICES = (
        ('reply', 'Generate Reply'),
        ('summarize', 'Summarize'),
        ('translate', 'Translate'),
        ('analyze', 'Analyze'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assistant_tasks')
    task_type = models.CharField(max_length=20, choices=TASK_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Input data
    input_text = models.TextField()
    context = models.JSONField(blank=True, null=True)
    
    # Output data
    output_text = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Metadata
    related_email_id = models.IntegerField(blank=True, null=True)
    processing_time = models.FloatField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'assistant_tasks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.task_type} - {self.status}'
