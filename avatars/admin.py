# avatars/admin.py

from django.contrib import admin
from .models import (
    Avatar,
    AvatarSource,
    AvatarTrainingJob,
    AvatarMemoryChunk,
    AvatarConversation,
    AvatarMessage,
    AvatarSettings,
    AvatarAnalytics,
)

# -----------------------
# Inline Models
# -----------------------

class AvatarSourceInline(admin.TabularInline):
    model = AvatarSource
    extra = 0
    readonly_fields = ("created_at",)


class AvatarSettingsInline(admin.StackedInline):
    model = AvatarSettings
    extra = 0
    readonly_fields = ("created_at", "updated_at")


class AvatarMessageInline(admin.TabularInline):
    model = AvatarMessage
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("role", "content", "created_at")


# -----------------------
# Main Avatar Admin
# -----------------------

@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    list_display = ("name", "handle", "owner", "trained", "trained_at", "created_at")
    search_fields = ("name", "handle", "owner__email")
    list_filter = ("trained", "created_at")
    readonly_fields = ("created_at", "trained_at")

    inlines = [
        AvatarSourceInline,
        AvatarSettingsInline,
    ]

    fieldsets = (
        ("Basic Info", {
            "fields": ("owner", "name", "handle", "photo"),
        }),
        ("Personality", {
            "fields": ("persona_prompt", "tone", "writing_style"),
        }),
        ("Training Status", {
            "fields": ("trained", "trained_at", "summary_knowledge"),
        }),
        ("Timestamps", {
            "fields": ("created_at",),
        }),
    )


# -----------------------
# Avatar Sources Admin
# -----------------------

@admin.register(AvatarSource)
class AvatarSourceAdmin(admin.ModelAdmin):
    list_display = ("avatar", "source_type", "enabled", "include_for_knowledge", "include_for_tone", "created_at")
    list_filter = ("source_type", "enabled", "include_for_knowledge", "include_for_tone")
    search_fields = ("avatar__name",)
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "avatar", "source_type", "enabled",
        "include_for_knowledge", "include_for_tone", "metadata",
        "created_at", "updated_at"
    )


# -----------------------
# Training Jobs
# -----------------------

@admin.register(AvatarTrainingJob)
class AvatarTrainingJobAdmin(admin.ModelAdmin):
    list_display = ("avatar", "status", "created_at", "started_at", "finished_at")
    list_filter = ("status", "created_at")
    search_fields = ("avatar__name",)
    readonly_fields = ("logs", "created_at", "started_at", "finished_at")

    fields = (
        "avatar", "status",
        "created_at", "started_at", "finished_at",
        "logs",
    )


# -----------------------
# Memory Chunks (Embeddings)
# -----------------------

@admin.register(AvatarMemoryChunk)
class AvatarMemoryChunkAdmin(admin.ModelAdmin):
    list_display = ("avatar", "source_type", "short_text", "created_at")
    search_fields = ("text", "avatar__name")
    list_filter = ("source_type",)
    readonly_fields = ("embedding", "created_at")

    def short_text(self, obj):
        return obj.text[:80] + "..." if len(obj.text) > 80 else obj.text


# -----------------------
# Conversations + Messages
# -----------------------

@admin.register(AvatarConversation)
class AvatarConversationAdmin(admin.ModelAdmin):
    list_display = ("avatar", "visitor_id", "started_at", "ended_at", "takeover")
    search_fields = ("avatar__name", "visitor_id")
    list_filter = ("takeover", "started_at")

    inlines = [AvatarMessageInline]

    readonly_fields = ("started_at", "ended_at")


@admin.register(AvatarMessage)
class AvatarMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "short_msg", "created_at")
    search_fields = ("content",)
    list_filter = ("role",)
    readonly_fields = ("created_at",)

    def short_msg(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content


# -----------------------
# Settings
# -----------------------

@admin.register(AvatarSettings)
class AvatarSettingsAdmin(admin.ModelAdmin):
    list_display = ("avatar", "response_delay_ms", "visibility", "created_at")
    search_fields = ("avatar__name",)
    readonly_fields = ("created_at", "updated_at")


# -----------------------
# Analytics
# -----------------------

@admin.register(AvatarAnalytics)
class AvatarAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("avatar", "total_visits", "total_messages", "last_interaction")
    readonly_fields = ("avatar",)
