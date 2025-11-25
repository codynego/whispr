# avatars/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Avatar,
    AvatarSource,
    AvatarTrainingJob,
    AvatarMemoryChunk,
    AvatarConversation,
    AvatarMessage,
)


@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    list_display = [
        "handle_link", "name", "owner", "purpose", "visibility",
        "trained_status", "total_conversations", "created_at"
    ]
    list_filter = ["visibility", "purpose", "tone_preset", "trained", "created_at"]
    search_fields = ["handle", "name", "owner__email", "owner__username"]
    readonly_fields = [
        "trained", "trained_at", "total_conversations", "total_messages",
        "persona_prompt", "summary_knowledge", "writing_style", "created_at", "updated_at"
    ]
    fieldsets = (
        ("Owner & Identity", {
            "fields": ("owner", "name", "handle", "photo", "purpose")
        }),
        ("Behavior", {
            "fields": ("tone_preset", "custom_tone_notes", "pinned_instructions")
        }),
        ("Chat Settings", {
            "fields": ("welcome_message", "suggested_questions", "collect_name", "collect_email", "calendly_link")
        }),
        ("Access & Privacy", {
            "fields": ("visibility", "protected_code", "store_conversations", "message_retention_days")
        }),
        ("Training State", {
            "fields": ("trained", "trained_at", "persona_prompt", "summary_knowledge", "writing_style"),
            "classes": ("collapse",)
        }),
        ("Analytics", {
            "fields": ("total_conversations", "total_messages", "tags"),
        }),
    )

    def handle_link(self, obj):
        url = f"https://whisone.com/@{obj.handle}"
        return format_html('<a href="{}" target="_blank">@{}</a>', url, obj.handle)
    handle_link.short_description = "Public Link"

    def trained_status(self, obj):
        if not obj.trained:
            return format_html('<span style="color: red;">Not trained</span>')
        return format_html('<span style="color: green;">Trained</span>')
    trained_status.short_description = "Training"


@admin.register(AvatarSource)
class AvatarSourceAdmin(admin.ModelAdmin):
    list_display = ["avatar", "source_type", "enabled", "include_for_tone", "include_for_knowledge", "created_at"]
    list_filter = ["source_type", "enabled", "include_for_tone"]
    search_fields = ["avatar__handle", "avatar__name"]


@admin.register(AvatarTrainingJob)
class AvatarTrainingJobAdmin(admin.ModelAdmin):
    list_display = ["avatar", "status", "started_at", "finished_at", "duration", "link"]
    list_filter = ["status", "started_at"]
    search_fields = ["avatar__handle", "avatar__name"]
    readonly_fields = ["avatar", "status", "logs", "error_message", "started_at", "finished_at"]

    def duration(self, obj):
        if not obj.started_at or not obj.finished_at:
            return "-"
        delta = obj.finished_at - obj.started_at
        return str(delta).split(".")[0]  # remove microseconds
    duration.short_description = "Duration"

    def link(self, obj):
        url = reverse("admin:avatars_avatartrainingjob_change", args=[obj.pk])
        return format_html('<a href="{}">View Logs</a>', url)
    link.short_description = ""


@admin.register(AvatarMemoryChunk)
class AvatarMemoryChunkAdmin(admin.ModelAdmin):
    list_display = ["avatar", "source_type", "text_preview", "created_at"]
    list_filter = ["source_type", "created_at"]
    search_fields = ["text", "avatar__handle"]

    def text_preview(self, obj):
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text
    text_preview.short_description = "Content"


@admin.register(AvatarConversation)
class AvatarConversationAdmin(admin.ModelAdmin):
    list_display = [
        "avatar", "visitor_info", "started_at", "duration", "message_count",
        "lead_score", "converted", "taken_over_by_owner"
    ]
    list_filter = ["avatar__purpose", "started_at", "converted", "taken_over_by_owner"]
    search_fields = ["visitor_id", "visitor_email", "visitor_name", "avatar__handle"]
    readonly_fields = ["avatar", "visitor_id", "started_at", "ended_at"]

    def visitor_info(self, obj):
        parts = []
        if obj.visitor_name:
            parts.append(obj.visitor_name)
        if obj.visitor_email:
            parts.append(f"<{obj.visitor_email}>")
        if not parts:
            return obj.visitor_id[:12]
        return " ".join(parts)
    visitor_info.allow_tags = True
    visitor_info.short_description = "Visitor"

    def duration(self, obj):
        if not obj.ended_at:
            return "Active"
        delta = obj.ended_at - obj.started_at
        return str(delta).split(".")[0]
    duration.short_description = "Duration"

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Messages"


@admin.register(AvatarMessage)
class AvatarMessageAdmin(admin.ModelAdmin):
    list_display = ["conversation", "role", "short_content", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["content", "conversation__avatar__handle"]

    def short_content(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content
    short_content.short_description = "Message"

    def has_add_permission(self, request):
        return False  # don't let admins manually create messages