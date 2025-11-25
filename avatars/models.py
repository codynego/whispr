# whisone/avatars/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
import uuid


class Avatar(models.Model):
    # Visibility
    VISIBILITY_CHOICES = [
        ("private", "Private"),
        ("protected", "Protected"),
        ("public", "Public"),
    ]

    # Main use cases
    PURPOSE_CHOICES = [
        ("personal", "Personal"),
        ("business", "Business"),
        ("support", "Customer Support"),
        ("fan", "Fan / Creator"),
        ("professional", "Professional / Consultant"),
        ("utility", "Utility / Assistant"),
    ]

    TONE_CHOICES = [
        ("casual", "Casual"),
        ("friendly", "Friendly"),
        ("professional", "Professional"),
        ("witty", "Witty"),
        ("sarcastic", "Sarcastic"),
        ("formal", "Formal"),
        ("custom", "Custom"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="avatars"
    )

    # Core identity
    name = models.CharField(max_length=100)
    handle = models.SlugField(max_length=120, unique=True, db_index=True)
    photo = models.ImageField(upload_to="avatars/photos/", null=True, blank=True)

    # Classification & behavior
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default="personal")
    tone_preset = models.CharField(max_length=30, choices=TONE_CHOICES, default="friendly")
    custom_tone_notes = models.TextField(blank=True, null=True)

    # Access control
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default="private")
    protected_code = models.CharField(max_length=100, blank=True, null=True)  # for protected avatars

    # Always-injected instructions (top of system prompt)
    pinned_instructions = models.TextField(
        blank=True,
        help_text="These instructions are always included first in the system prompt (e.g. rates, boundaries, disclaimers)."
    )

    # Chat behavior & UX
    welcome_message = models.TextField(
        blank=True,
        help_text="First message the avatar sends when someone starts a chat."
    )
    suggested_questions = models.JSONField(
        default=list,
        blank=True,
        help_text='Example: ["What services do you offer?", "How can I book a session?"]'
    )

    # Lead capture
    collect_name = models.BooleanField(default=False, help_text="Ask visitor for name")
    collect_email = models.BooleanField(default=False, help_text="Ask visitor for email")
    calendly_link = models.URLField(blank=True, null=True)

    # Privacy & compliance
    store_conversations = models.BooleanField(
        default=True,
        help_text="If False, messages are deleted immediately after the session ends (required for therapists, lawyers, etc.)"
    )
    message_retention_days = models.PositiveIntegerField(
        default=90,
        validators=[MinValueValidator(1)],
        help_text="Auto-delete conversations older than this (0 = forever)"
    )

    # Notifications
    notify_email = models.BooleanField(default=True)

    # Training state
    persona_prompt = models.TextField(blank=True, null=True)
    summary_knowledge = models.TextField(blank=True, null=True)
    writing_style = models.TextField(blank=True, null=True)

    trained = models.BooleanField(default=False)
    trained_at = models.DateTimeField(null=True, blank=True)

    # Analytics
    total_conversations = models.PositiveIntegerField(default=0)
    total_messages = models.PositiveIntegerField(default=0)

    # Metadata & discoverability
    tags = models.JSONField(default=list, blank=True)  # e.g. ["fitness", "berlin", "coach"]
    is_featured = models.BooleanField(default=False)

    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["handle"]),
            models.Index(fields=["owner", "is_deleted"]),
            models.Index(fields=["is_featured", "visibility"]),
        ]
        ordering = ["-created_at"]

    def mark_trained(self):
        self.trained = True
        self.trained_at = timezone.now()
        self.save(update_fields=["trained", "trained_at"])

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.visibility = "private"
        self.save()

    def __str__(self):
        return f"@{self.handle} – {self.name} ({self.owner})"


class AvatarSource(models.Model):
    SOURCE_TYPES = [
        ("whatsapp", "WhatsApp Chats"),
        ("notes", "Whisone Notes"),
        ("gmail", "Gmail Emails"),
        ("uploads", "File Uploads"),
        ("website", "Website / Links"),
        ("manual", "Manual Input"),
        ("calendar", "Calendar"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="sources")

    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)
    metadata = models.JSONField(default=dict)
    include_for_tone = models.BooleanField(default=True)
    include_for_knowledge = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_source_type_display()} → @{self.avatar.handle}"


class AvatarTrainingJob(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="training_jobs")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    logs = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def add_log(self, text: str):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs = (self.logs or "") + f"[{timestamp}] {text}\n"
        self.save(update_fields=["logs"])

    def __str__(self):
        return f"Training #{self.id[:8]} – @{self.avatar.handle} [{self.status}]"


class AvatarMemoryChunk(models.Model):
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="chunks")

    chunk_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    text = models.TextField()
    source_type = models.CharField(max_length=50)
    metadata = models.JSONField(default=dict, blank=True)

    # Use django-pgvector's VectorField in production
    embedding = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["avatar"]),
            models.Index(fields=["source_type"]),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_id} ({self.source_type})"


class AvatarConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="conversations")

    visitor_id = models.CharField(max_length=200, db_index=True)  # anonymized
    visitor_name = models.CharField(max_length=100, blank=True, null=True)
    visitor_email = models.EmailField(blank=True, null=True)

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(auto_now=True)

    taken_over_by_owner = models.BooleanField(default=False)
    lead_score = models.SmallIntegerField(default=0)
    converted = models.BooleanField(default=False)

    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"Chat {self.id} with @{self.avatar.handle}"


class AvatarMessage(models.Model):
    ROLE_CHOICES = [
        ("visitor", "Visitor"),
        ("avatar", "Avatar"),
        ("owner", "Owner (Takeover)"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        AvatarConversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()

    model_used = models.CharField(max_length=50, blank=True)  # e.g. gpt-4o, claude-3.5
    tokens_used = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}{'...' if len(self.content) > 50 else ''}"