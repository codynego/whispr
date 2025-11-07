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


TASK_TYPE_CHOICES = (
        # 📨 Email-related
        ('summarize_email', 'Summarize Email'),
        ('reply_email', 'Reply to Email'),
        ('send_email', 'Send Email'),
        ('analyze_email', 'Analyze Email Content'),
        ('classify_email', 'Classify Email Topic'),

        # 💬 Communication & Notes
        ('reminder', 'Set Reminder'),
        ('follow_up', 'Send Follow-up'),
        ('meeting_note', 'Meeting Summary or Note'),
        ('translate_message', 'Translate Message'),

        # 📊 Productivity & Workflow
        ('daily_digest', 'Daily Email Digest'),
        ('weekly_report', 'Weekly Summary Report'),
        ('alert', 'Important Email Alert'),
        ('task_summary', 'Summarize Tasks or Progress'),

        # ⚙️ Smart Automations
        ('auto_reply', 'Automatic Email Reply'),
        ('auto_summarize', 'Auto Summarize New Messages'),
        ('auto_followup', 'Auto Follow-Up'),
        ('smart_notify', 'Smart Notification for Key Emails'),
        ('auto_categorize', 'Automatically Categorize Emails'),

        # 🧠 Insights
        ('priority_rank', 'Rank Emails by Priority'),
        ('sentiment_analysis', 'Analyze Email Sentiment'),

        # ⚡ Generic / Catch-all
        ('custom', 'Custom Task'),
    )


class AssistantTask(models.Model):
    """Model to store AI assistant tasks and reminders."""



    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('scheduled', 'Scheduled'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assistant_tasks'
    )
    task_type = models.CharField(max_length=30, choices=TASK_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Input / output data
    input_text = models.TextField()
    context = models.JSONField(blank=True, null=True)
    output_text = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    # Metadata
    related_email_id = models.IntegerField(blank=True, null=True)
    processing_time = models.FloatField(blank=True, null=True)

    # ⏰ Scheduling fields
    due_datetime = models.DateTimeField(blank=True, null=True, help_text="Time to trigger the task")
    is_recurring = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(
        max_length=100, blank=True, null=True, help_text="e.g., daily, weekly, every Monday"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'assistant_tasks'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_type} - {self.status}"

    @property
    def is_due(self):
        """Check if the task is ready to execute."""
        from django.utils import timezone
        return self.due_datetime and self.due_datetime <= timezone.now()



from django.db import models
from django.conf import settings
from django.utils import timezone

class Automation(models.Model):
    """User-defined automation for Whisone personal assistant."""

    # --- Core ---
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="automations"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    # --- Trigger types ---
    TRIGGER_TYPES = (
        ("on_email_received", "On Email Received"),
        ("on_schedule", "On Schedule"),
        ("on_message_received", "On Message Received"),
        ("on_task_due", "On Task Due"),
        ("on_calendar_event", "On Calendar Event"),
        ("manual", "Manual Trigger"),
    )
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_TYPES)

    # Optional: Specific trigger data (e.g., sender email, time, day, keywords)
    trigger_condition = models.JSONField(blank=True, null=True, help_text="Extra data for the trigger logic")

    # --- Action types ---

    action_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)
    metadata = models.JSONField(blank=True, null=True, help_text="Extra parameters for the action")

    # --- Schedule support ---
    status = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(blank=True, null=True)
    next_run_at = models.DateTimeField(blank=True, null=True)
    recurrence_pattern = models.CharField(max_length=100, blank=True, null=True)

    # --- Metadata ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "assistant_automations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.trigger_type})"

    def should_trigger(self, context=None):
        """Checks if automation should run, based on trigger and conditions."""
        if not self.is_active:
            return False

        # Time-based trigger check
        if self.trigger_type == "on_schedule" and self.next_run_at:
            return timezone.now() >= self.next_run_at

        # Other context-based triggers (email, message, etc.)
        if self.trigger_type in ["on_email_received", "on_message_received"] and context:
            sender = context.get("sender")
            keywords = context.get("keywords", [])
            cond = self.trigger_condition or {}
            if cond.get("from") and cond["from"].lower() != sender.lower():
                return False
            if cond.get("contains") and not any(k in context.get("text", "") for k in cond["contains"]):
                return False

        return True

    def mark_triggered(self):
        """Update timestamps when automation runs."""
        self.last_triggered_at = timezone.now()
        self.save(update_fields=["last_triggered_at"])
