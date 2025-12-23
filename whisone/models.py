from django.db import models
from django.conf import settings


# -----------------------------
# 1. Reminder
# -----------------------------

class BaseModel(models.Model):
    embedding = models.JSONField(
        blank=True,
        null=True,
        help_text="Vector embedding for semantic search."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Reminder(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    remind_at = models.DateTimeField()
    completed = models.BooleanField(default=False)


    def __str__(self):
        return f"{self.text} at {self.remind_at}"

# -----------------------------
# 2. Note
# -----------------------------
class Note(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField()

    def __str__(self):
        return self.content[:50]

# -----------------------------
# 3. Todo
# -----------------------------
class Todo(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.TextField()
    done = models.BooleanField(default=False)
    def __str__(self):
        return self.task

# -----------------------------
# 4. Integration (email, calendar, whatsapp)
# -----------------------------
class Integration(models.Model):
    PROVIDERS = [
        ("gmail", "Gmail"),
        ("outlook", "Outlook"),
        ("google_calendar", "Google Calendar"),
        ("whatsapp_business", "WhatsApp Business"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    provider = models.CharField(max_length=50, choices=PROVIDERS)

    # Unique identifier per provider (email, calendar ID, phone number, etc)
    external_id = models.CharField(max_length=255)

    # OAuth credentials
    access_token = models.TextField()
    refresh_token = models.TextField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Metadata (optional but very useful)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "provider", "external_id")

    def __str__(self):
        return f"{self.user} — {self.provider} ({self.external_id})"




class AutomationRule(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="automation_rules")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    # Trigger options: email, calendar, reminder, note, daily_schedule, etc.
    TRIGGER_CHOICES = [
        ("email_received", "Email Received"),
        ("calendar_event", "Calendar Event"),
        ("daily_schedule", "Daily Schedule"),
        ("note_created", "Note Created"),
        ("reminder_due", "Reminder Due"),
    ]
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    trigger_params = models.JSONField(default=dict, blank=True)  # e.g., {"from": "boss@example.com"}

    # Optional conditions
    conditions = models.JSONField(default=dict, blank=True)  # e.g., {"subject_contains": "Meeting"}

    # Actions to perform
    actions = models.JSONField(default=list, blank=True)  
    # e.g., [{"action": "create_reminder", "params": {"title": "Follow up"}}]

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"



import json

from django.db import models
from django.conf import settings
import uuid


# whisone/models.py
class DailySummary(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    summary_date = models.DateField()
    summary_text = models.TextField()
    raw_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)







import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Memory(models.Model):
    MEMORY_TYPES = [
        ("emotional", "Emotional"),
        ("goal", "Goal"),
        ("learning", "Learning"),
        ("task", "Task"),
        ("event", "Life Event"),
        ("reflection", "Reflection"),
        ("relationship", "Relationship"),
    ]

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="memories"
    )

    # Core content
    raw_text = models.TextField()
    summary = models.TextField()

    # Classification
    memory_type = models.CharField(
        max_length=20, choices=MEMORY_TYPES
    )

    emotion = models.CharField(
        max_length=50, null=True, blank=True
    )
    sentiment = models.FloatField(
        null=True, blank=True
    )  # range: -1 → 1

    importance = models.FloatField(default=0.5)  # 0 → 1
    context = models.JSONField(default=dict)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    embedding = models.JSONField(blank=True, null=True)  # AI embedding of the content

    def __str__(self):
        return f"{self.memory_type} | {self.summary[:50]}"



from django.db import models
from django.conf import settings

def user_upload_path(instance, filename):
    # Files will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f"user_{instance.user.id}/{filename}"

class UploadedFile(models.Model):
    FILE_TYPES = (
        ('pdf', 'PDF'),
        ('docx', 'Word Document'),
        ('txt', 'Text File'),
        ('csv', 'CSV File'),
        ('image', 'Image File'),
        ('other', 'Other'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_files'
    )

    file = models.FileField(upload_to=user_upload_path)
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default='other')
    original_filename = models.CharField(max_length=255)
    size = models.BigIntegerField(null=True, blank=True)  # bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)  # whether text has been extracted
    content = models.TextField(blank=True, null=True)  # extracted text from the file
    embedding = models.JSONField(blank=True, null=True)  # AI embedding of the content

    def save(self, *args, **kwargs):
        # Capture original filename and size
        self.original_filename = self.file.name
        self.size = self.file.size

        # Auto-detect file type
        ext = self.file.name.lower()
        if ext.endswith('.pdf'):
            self.file_type = 'pdf'
        elif ext.endswith('.docx'):
            self.file_type = 'docx'
        elif ext.endswith('.txt'):
            self.file_type = 'txt'
        elif ext.endswith('.csv'):
            self.file_type = 'csv'
        elif ext.endswith(('.png', '.jpg', '.jpeg')):
            self.file_type = 'image'
        else:
            self.file_type = 'other'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.original_filename}"
