# from django.db import models
# from django.conf import settings


# class ChannelAccount(models.Model):
#     """
#     Stores account configurations for any integrated communication channel
#     (e.g., Gmail, Outlook, WhatsApp Business API, Slack Bot, Telegram Bot, etc.)
#     """
#     CHANNEL_CHOICES = [
#         ("email", "Email"),
#         ("whatsapp", "WhatsApp"),
#         ("slack", "Slack"),
#         ("telegram", "Telegram"),
#     ]

#     PROVIDER_CHOICES = [
#         ("gmail", "Gmail"),
#         ("outlook", "Outlook"),
#         ("meta", "Meta (WhatsApp)"),
#         ("slack", "Slack"),
#         ("telegram", "Telegram"),
#     ]

#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="channel_accounts"
#     )
#     channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
#     provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
#     address_or_id = models.CharField(max_length=255)  # e.g. email, phone number, bot ID
#     access_token = models.TextField(blank=True, null=True)
#     refresh_token = models.TextField(blank=True, null=True)
#     token_expires_at = models.DateTimeField(blank=True, null=True)
#     is_active = models.BooleanField(default=True)
#     last_synced = models.DateTimeField(blank=True, null=True)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = "channel_accounts"
#         unique_together = ("user", "channel", "address_or_id")

#     def __str__(self):
#         return f"{self.address_or_id} ({self.provider})"


# class Conversation(models.Model):
#     account = models.ForeignKey('ChannelAccount', on_delete=models.CASCADE, related_name='conversations')
#     thread_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)  # Gmail, Slack thread_ts, WhatsApp chat_id
#     channel = models.CharField(max_length=50)
#     title = models.CharField(max_length=255, blank=True, null=True)
#     last_message_at = models.DateTimeField(blank=True, null=True)
#     last_sender = models.CharField(max_length=255, blank=True, null=True)
#     summary = models.TextField(blank=True, null=True)
#     next_step_suggestion = models.TextField(blank=True, null=True)
#     actionable_data = models.JSONField(blank=True, null=True)
#     people_and_orgs = models.JSONField(blank=True, null=True)
#     is_archived = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = "conversations"
#         ordering = ["-last_message_at"]

#     def __str__(self):
#         return f"{self.title or self.thread_id or self.channel}"



# from django.db import models
# from django.utils import timezone


# class Message(models.Model):
#     """
#     Unified message model for any communication platform (Email, WhatsApp, Slack, etc.)
#     Includes AI-generated insights for summaries, importance scoring, and contextual intelligence.
#     """
#     IMPORTANCE_CHOICES = [
#         ("low", "Low"),
#         ("medium", "Medium"),
#         ("high", "High"),
#         ("critical", "Critical"),
#     ]

#     conversation = models.ForeignKey("Conversation", on_delete=models.CASCADE, related_name="messages")
#     channel = models.CharField(max_length=50, default="email", db_index=True)
#     account = models.ForeignKey("ChannelAccount", on_delete=models.CASCADE, related_name="messages")

#     external_id = models.CharField(max_length=255, unique=True, db_index=True)  # message_id, ts, etc.
#     sender = models.CharField(max_length=255)
#     sender_name = models.CharField(max_length=255, blank=True, null=True)
#     recipients = models.JSONField(default=list)

#     content = models.TextField(blank=True, null=True)  # Plain text or main message body
#     metadata = models.JSONField(default=dict, blank=True)  # Holds platform-specific data (e.g., email headers, WhatsApp payload)
#     attachments = models.JSONField(default=list, blank=True)

#     # ===== AI and Importance Analytics =====
#     importance = models.CharField(max_length=20, choices=IMPORTANCE_CHOICES, default="medium")
#     importance_score = models.FloatField(default=0.5)
#     importance_analysis = models.TextField(blank=True, null=True)

#     ai_summary = models.TextField(blank=True, null=True)
#     ai_next_step = models.TextField(blank=True, null=True)
#     ai_people = models.JSONField(default=list, blank=True, null=True)
#     ai_organizations = models.JSONField(default=list, blank=True, null=True)
#     ai_related = models.JSONField(default=list, blank=True, null=True)

#     analyzed_at = models.DateTimeField(blank=True, null=True)

#     # ===== Embeddings =====
#     embedding = models.JSONField(blank=True, null=True)
#     embedding_generated = models.BooleanField(default=False)

#     # ===== Flags =====
#     is_read = models.BooleanField(default=False)
#     is_starred = models.BooleanField(default=False)
#     is_incoming = models.BooleanField(default=True)

#     sent_at = models.DateTimeField()
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = "messages"
#         ordering = ["-sent_at"]
#         indexes = [
#             models.Index(fields=["-sent_at"]),
#             models.Index(fields=["importance"]),
#             models.Index(fields=["is_read"]),
#         ]

#     def __str__(self):
#         return f"{self.channel.upper()} | {self.sender}: {self.content[:60]}"



# class UserRule(models.Model):
#     """
#     Flexible user-defined rules for prioritization or classification across all channels.
#     Works for emails, WhatsApp, Slack messages, etc.
#     """
#     RULE_TYPES = [
#         ("sender", "Sender Address/ID"),
#         ("keyword", "Keyword in Message"),
#         ("subject", "Subject Contains (Email only)"),
#         ("body", "Body/Text Contains"),
#         ("attachment", "Has Attachment"),
#         ("reply", "Is a Reply/Thread"),
#         ("ai", "AI Context Rule"),
#     ]

#     IMPORTANCE_CHOICES = [
#         ("low", "Low"),
#         ("medium", "Medium"),
#         ("high", "High"),
#         ("critical", "Critical"),
#     ]

#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rules")
#     name = models.CharField(max_length=255)
#     rule_type = models.CharField(max_length=50, choices=RULE_TYPES)
#     channel = models.CharField(max_length=50, blank=True, null=True)  # optional: apply only to one channel
#     value = models.TextField(
#         blank=True, null=True, help_text="Email, keyword(s), or pattern depending on rule type"
#     )
#     importance = models.CharField(max_length=20, choices=IMPORTANCE_CHOICES, default="medium")
#     is_active = models.BooleanField(default=True)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         verbose_name = "User Rule"
#         verbose_name_plural = "User Rules"
#         ordering = ["-created_at"]

#     def __str__(self):
#         return f"{self.user.email} - {self.name} ({self.rule_type})"

from django.db import models
from django.conf import settings
from django.utils import timezone
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import json
from django.core.exceptions import ImproperlyConfigured

# Key derivation for Fernet key from SECRET_KEY
def get_fernet_key():
    """
    Derive a Fernet key from Django's SECRET_KEY for encryption.
    This ensures the key is consistent across app restarts but secure.
    In production, consider using a dedicated secret or env var for the key.
    """
    if not settings.SECRET_KEY:
        raise ImproperlyConfigured("SECRET_KEY must be set for encryption.")
    
    # Use PBKDF2 to derive a 32-byte key from SECRET_KEY
    password = settings.SECRET_KEY.encode()
    salt = b'salt_for_messages'  # Fixed salt; in prod, use a random salt stored securely
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return Fernet(key)

# Global Fernet instance (thread-safe in Django)
cipher_suite = get_fernet_key()


class EncryptedTextField(models.TextField):
    """
    Custom field to encrypt text on save and decrypt on fetch.
    Uses Fernet symmetric encryption with a key derived from SECRET_KEY.
    Handles legacy plaintext data gracefully.
    """
    description = "An encrypted text field"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return value
        return cipher_suite.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            return cipher_suite.decrypt(value.encode()).decode()
        except InvalidToken:
            # Legacy plaintext data - return as is
            return value

    def get_internal_type(self):
        return "TextField"


class EncryptedJSONField(models.JSONField):
    """
    Custom field to encrypt JSON data on save and decrypt on fetch.
    Handles legacy plaintext JSON data.
    """
    description = "An encrypted JSON field"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return value
        json_str = json.dumps(value)
        return cipher_suite.encrypt(json_str.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            decrypted = cipher_suite.decrypt(value.encode()).decode()
            return json.loads(decrypted)
        except (InvalidToken, json.JSONDecodeError):
            # Legacy plaintext JSON - try to parse directly
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value  # Fallback if invalid

    def get_internal_type(self):
        return "JSONField"


class ChannelAccount(models.Model):
    """
    Stores account configurations for any integrated communication channel
    (e.g., Gmail, Outlook, WhatsApp Business API, Slack Bot, Telegram Bot, etc.)
    Tokens are encrypted at rest.
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
    access_token = EncryptedTextField(blank=True, null=True)  # Encrypted
    refresh_token = EncryptedTextField(blank=True, null=True)  # Encrypted
    token_expires_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(blank=True, null=True)
    last_history_id = models.CharField(max_length=255, null=True, blank=True)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "channel_accounts"
        unique_together = ("user", "channel", "address_or_id")

    def __str__(self):
        return f"{self.address_or_id} ({self.provider})"

    def save(self, *args, **kwargs):
        """
        Ensure tokens are encrypted before saving.
        """
        super().save(*args, **kwargs)


class Conversation(models.Model):
    account = models.ForeignKey('ChannelAccount', on_delete=models.CASCADE, related_name='conversations')
    thread_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)  # Gmail, Slack thread_ts, WhatsApp chat_id
    channel = models.CharField(max_length=50)
    title = models.CharField(max_length=255, blank=True, null=True)
    last_message_at = models.DateTimeField(blank=True, null=True)
    last_sender = models.CharField(max_length=255, blank=True, null=True)
    summary = EncryptedTextField(blank=True, null=True)  # Encrypted
    next_step_suggestion = EncryptedTextField(blank=True, null=True)  # Encrypted
    actionable_data = EncryptedJSONField(blank=True, null=True, default=dict)  # Encrypted JSON
    people_and_orgs = EncryptedJSONField(blank=True, null=True, default=dict)  # Encrypted JSON
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
    Includes AI-generated insights for summaries, importance scoring, and contextual intelligence.
    Sensitive fields (content, metadata, attachments, AI fields) are encrypted at rest.
    """
    IMPORTANCE_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    LABEL_CHOICES = [
        ("important", "Important"),
        ("personal", "Personal"),
        ("work", "Work"),
        ("follow_up", "Follow Up"),
        ("spam", "Spam"),
        ("other", "Other"),
    ]

    conversation = models.ForeignKey("Conversation", on_delete=models.CASCADE, related_name="messages")
    channel = models.CharField(max_length=50, default="email", db_index=True)
    account = models.ForeignKey("ChannelAccount", on_delete=models.CASCADE, related_name="messages")

    external_id = models.CharField(max_length=255, unique=True, db_index=True)  # message_id, ts, etc.
    sender = models.CharField(max_length=255)
    sender_name = models.CharField(max_length=255, blank=True, null=True)
    recipients = EncryptedJSONField(default=list, blank=True)  # Encrypted JSON

    content = EncryptedTextField(blank=True, null=True)  # Encrypted main content
    metadata = EncryptedJSONField(default=dict, blank=True)  # Encrypted platform-specific data
    attachments = EncryptedJSONField(default=list, blank=True)  # Encrypted attachments info

    # ===== AI and Importance Analytics =====
    importance = models.CharField(max_length=20, choices=IMPORTANCE_CHOICES, default="medium")
    importance_score = models.FloatField(default=0.5)
    importance_analysis = EncryptedTextField(blank=True, null=True)  # Encrypted

    ai_summary = EncryptedTextField(blank=True, null=True)  # Encrypted
    ai_next_step = EncryptedTextField(blank=True, null=True)  # Encrypted
    ai_people = EncryptedJSONField(default=list, blank=True, null=True)  # Encrypted
    ai_organizations = EncryptedJSONField(default=list, blank=True, null=True)  # Encrypted
    ai_related = EncryptedJSONField(default=list, blank=True, null=True)  # Encrypted

    label = models.CharField(
        max_length=50,
        choices=LABEL_CHOICES,
        blank=True,
        null=True,
        help_text="AI or user-assigned label for message"
    )

    analyzed_at = models.DateTimeField(blank=True, null=True)

    # ===== Embeddings =====
    embedding = models.JSONField(blank=True, null=True)  # Embeddings are vectors, not sensitive text; left unencrypted for efficiency
    embedding_generated = models.BooleanField(default=False)

    # ===== Flags =====
    is_read = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    is_incoming = models.BooleanField(default=True)

    sent_at = models.DateTimeField()
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
        # Decrypt content for __str__ if needed, but keep it short
        content_preview = self.content[:60] if self.content else "No content"
        return f"{self.channel.upper()} | {self.sender}: {content_preview}"


class UserRule(models.Model):
    """
    Flexible user-defined rules for prioritization or classification across all channels.
    Works for emails, WhatsApp, Slack messages, etc.
    No encryption needed here as rules are user-defined and not highly sensitive.
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