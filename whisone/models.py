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

import uuid
from django.db import models
from django.conf import settings

class KnowledgeVaultEntry(models.Model):
    """
    Stores a single knowledge memory extracted from user interactions.
    Includes structured entities + embeddings for semantic search.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="knowledge_entries"
    )

    memory_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    # ----- CORE MEMORY FIELDS -----
    summary = models.TextField(
        blank=True,
        null=True,
        help_text="Natural language summary of this memory."
    )

    entities = models.JSONField(
        default=dict,
        help_text="Structured entities: { events:[], emotions:[], people:[], ... }"
    )

    relationships = models.JSONField(
        default=list,
        help_text="List of entity relationships."
    )

    # ----- SEARCH / SEMANTIC FIELDS -----
    text_search = models.TextField(
        blank=True,
        null=True,
        help_text="Flattened text used for text-based search."
    )

    embedding = models.JSONField(
        blank=True,
        null=True,
        help_text="Vector embedding for semantic search."
    )

    # ----- TIMESTAMPS -----
    timestamp = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Memory {self.memory_id} | {self.user.email}"
