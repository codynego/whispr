from django.db import models
from django.conf import settings


class ChannelAccount(models.Model):
    """
    Stores account configurations for any integrated communication channel
    (e.g., Gmail, Outlook, WhatsApp Business API, Slack Bot, Telegram Bot, etc.)
    """
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("slack", "Slack"),
        ("telegram", "Telegram"),
    ]

    PROVIDER_CHOICES = [
        ("gmail", "Gmail"),
        ("outlook", "Outlook"),
        ("meta", "Meta (WhatsApp)"),
        ("slack", "Slack"),
        ("telegram", "Telegram"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="channel_accounts"
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    address_or_id = models.CharField(max_length=255)  # e.g. email, phone number, bot ID
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "channel_accounts"
        unique_together = ("user", "channel", "address_or_id")

    def __str__(self):
        return f"{self.address_or_id} ({self.provider})"


class Conversation(models.Model):
    account = models.ForeignKey('ChannelAccount', on_delete=models.CASCADE, related_name='conversations')
    thread_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)  # Gmail, Slack thread_ts, WhatsApp chat_id
    channel = models.CharField(max_length=50)
    title = models.CharField(max_length=255, blank=True, null=True)
    last_message_at = models.DateTimeField(blank=True, null=True)
    last_sender = models.CharField(max_length=255, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    next_step_suggestion = models.TextField(blank=True, null=True)
    actionable_data = models.JSONField(blank=True, null=True)
    people_and_orgs = models.JSONField(blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations"
        ordering = ["-last_message_at"]

    def __str__(self):
        return f"{self.title or self.thread_id or self.channel}"



class Message(models.Model):
    """
    Unified message model for any communication platform (Email, WhatsApp, Slack, etc.)
    """
    IMPORTANCE_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    channel = models.CharField(max_length=50, default="email", db_index=True)
    account = models.ForeignKey(ChannelAccount, on_delete=models.CASCADE, related_name="messages")

    external_id = models.CharField(max_length=255, unique=True, db_index=True)  # message_id, ts, etc.
    sender = models.CharField(max_length=255)
    sender_name = models.CharField(max_length=255, blank=True, null=True)
    recipients = models.JSONField(default=list)

    content = models.TextField(blank=True, null=True)  # Plain text message body
    metadata = models.JSONField(default=dict, blank=True)  # Holds platform-specific data
    attachments = models.JSONField(default=list, blank=True)

    importance = models.CharField(max_length=20, choices=IMPORTANCE_CHOICES, default="medium")
    importance_score = models.FloatField(default=0.5)
    importance_analysis = models.TextField(blank=True, null=True)

    is_read = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    is_incoming = models.BooleanField(default=True)

    sent_at = models.DateTimeField()
    analyzed_at = models.DateTimeField(blank=True, null=True)

    embedding = models.JSONField(blank=True, null=True)
    embedding_generated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "messages"
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["-sent_at"]),
            models.Index(fields=["importance"]),
            models.Index(fields=["is_read"]),
        ]

    def __str__(self):
        return f"{self.channel.upper()} | {self.sender}: {self.content[:60]}"


class UserRule(models.Model):
    """
    Flexible user-defined rules for prioritization or classification across all channels.
    Works for emails, WhatsApp, Slack messages, etc.
    """
    RULE_TYPES = [
        ("sender", "Sender Address/ID"),
        ("keyword", "Keyword in Message"),
        ("subject", "Subject Contains (Email only)"),
        ("body", "Body/Text Contains"),
        ("attachment", "Has Attachment"),
        ("reply", "Is a Reply/Thread"),
        ("ai", "AI Context Rule"),
    ]

    IMPORTANCE_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=50, choices=RULE_TYPES)
    channel = models.CharField(max_length=50, blank=True, null=True)  # optional: apply only to one channel
    value = models.TextField(
        blank=True, null=True, help_text="Email, keyword(s), or pattern depending on rule type"
    )
    importance = models.CharField(max_length=20, choices=IMPORTANCE_CHOICES, default="medium")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Rule"
        verbose_name_plural = "User Rules"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.name} ({self.rule_type})"
