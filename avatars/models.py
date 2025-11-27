# whisone/avatars/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

# ----------------------------
# Core Models
# ----------------------------

class Avatar(models.Model):
    """
    Represents an AI personality / user clone
    """
    TONE_CHOICES = [
        ("casual", "Casual"),
        ("friendly", "Friendly"),
        ("professional", "Professional"),
        ("witty", "Witty"),
        ("formal", "Formal"),
        ("custom", "Custom"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avatars")
    name = models.CharField(max_length=100)
    handle = models.SlugField(max_length=120, unique=True)
    photo = models.ImageField(upload_to="avatars/photos/", null=True, blank=True)
    tone = models.CharField(max_length=30, choices=TONE_CHOICES, default="casual")
    persona_prompt = models.TextField(blank=True, null=True)
    trained = models.BooleanField(default=False)
    trained_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_trained(self):
        self.trained = True
        self.trained_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.name} ({self.owner})"


class AvatarConversation(models.Model):
    """
    Tracks a visitor chat session with an avatar
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="conversations")
    visitor_id = models.CharField(max_length=200)  # hashed IP / session ID
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    taken_over_by_owner = models.BooleanField(default=False)

    def __str__(self):
        return f"Conversation {self.id} with {self.avatar.handle}"


class AvatarMessage(models.Model):
    """
    Stores messages in a conversation
    """
    ROLE_CHOICES = [
        ("visitor", "Visitor"),
        ("avatar", "Avatar"),
        ("owner", "Owner Takeover"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(AvatarConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:30]}"


# ----------------------------
# Optional / Advanced Models
# ----------------------------

class AvatarSource(models.Model):
    """
    Stores sources of knowledge for training the avatar
    """
    SOURCE_TYPES = [
        ("whatsapp", "WhatsApp Chats"),
        ("notes", "Whisone Notes"),
        ("gmail", "Gmail Emails"),
        ("uploads", "File Uploads"),
        ("manual", "Manual Q&A / Tone Form"),
        ("calendar", "Calendar Events"),
        ("reminders", "Reminders"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="sources")
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPES)
    metadata = models.JSONField(default=dict)  # e.g., chat IDs, email labels, file IDs
    include_for_tone = models.BooleanField(default=True)
    include_for_knowledge = models.BooleanField(default=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source_type} → {self.avatar.name}"


class AvatarTrainingJob(models.Model):
    """
    Tracks background AI training tasks for the avatar
    """
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("error", "Error"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="training_jobs")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    logs = models.TextField(blank=True, null=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def add_log(self, text):
        self.logs = (self.logs or "") + f"[{timezone.now()}] {text}\n"
        self.save()

    def __str__(self):
        return f"TrainingJob({self.avatar.name}) - {self.status}"


class AvatarMemoryChunk(models.Model):
    """
    Stores chunks of knowledge / embeddings for AI responses
    """
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="chunks")
    chunk_id = models.UUIDField(default=uuid.uuid4, editable=False)
    text = models.TextField()
    source_type = models.CharField(max_length=50)
    embedding = models.JSONField(null=True, blank=True)  # optional if using vector DB
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["avatar"]),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_id} ({self.source_type})"


class AvatarAnalytics(models.Model):
    """
    Tracks basic usage metrics per avatar
    """
    avatar = models.ForeignKey(Avatar, on_delete=models.CASCADE, related_name="analytics")
    visitors_count = models.IntegerField(default=0)
    total_conversations = models.IntegerField(default=0)
    total_messages = models.IntegerField(default=0)
    last_active_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Analytics for {self.avatar.name}"


class AvatarSettings(models.Model):
    """
    Advanced per-avatar configuration
    """
    avatar = models.OneToOneField(Avatar, on_delete=models.CASCADE, related_name="settings")
    async_delay_seconds = models.IntegerField(default=5)
    visibility = models.CharField(max_length=20, choices=[("private","Private"), ("protected","Protected"), ("public","Public")], default="private")
    protected_code = models.CharField(max_length=100, blank=True, null=True)
    allow_owner_takeover = models.BooleanField(default=True)

    def __str__(self):
        return f"Settings for {self.avatar.name}"
