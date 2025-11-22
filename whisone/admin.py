from django.contrib import admin
from .models import Note, Reminder, Todo, Integration, AutomationRule, DailySummary


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'summary_date', 'created_at')
    search_fields = ('user__username', 'summary_text')
    readonly_fields = ('created_at', 'raw_data')

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'content', 'created_at')
    search_fields = ('content', 'user__username')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'text', 'remind_at', 'completed')
    search_fields = ('text', 'user__username')
    list_filter = ('completed',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'task', 'done')
    search_fields = ('task', 'user__username')
    list_filter = ('done',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Integration)
class IntegrationAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "external_id", "is_active", "created_at", "updated_at")
    list_filter = ("provider", "is_active")
    search_fields = ("user__username", "external_id")
    readonly_fields = ("created_at", "updated_at")  # timestamps are read-only
    ordering = ("-created_at",)

    fieldsets = (
        (None, {
            "fields": ("user", "provider", "external_id", "access_token", "refresh_token", "expires_at", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

# whisone/admin.pu

@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "trigger_type", "is_active", "created_at", "updated_at")
    list_filter = ("trigger_type", "is_active")
    search_fields = ("name", "user__username")
    readonly_fields = ("created_at", "updated_at")  # Only include fields that exist on the model
    ordering = ("-created_at",)

    fieldsets = (
        (None, {
            "fields": ("user", "name", "description", "trigger_type", "trigger_params", "conditions", "actions", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )



from django.contrib import admin
from django.utils.html import format_html
import json
from .models import KnowledgeVaultEntry


@admin.register(KnowledgeVaultEntry)
class KnowledgeVaultEntryAdmin(admin.ModelAdmin):
    list_display = (
        "memory_id",
        "user",
        "summary_snippet",
        "formatted_entities",
        "timestamp",
    )

    list_filter = (
        "user",
        "timestamp",
        "last_accessed",
    )

    search_fields = (
        "memory_id",
        "user__username",
        "user__email",
        "summary",
        "text_search",
    )

    readonly_fields = (
        "memory_id",
        "timestamp",
        "last_accessed",
        "pretty_entities",
        "pretty_relationships",
        "embedding",
        "text_search",
    )

    fieldsets = (
        ("Memory Info", {
            "fields": ("memory_id", "user", "summary", "timestamp", "last_accessed")
        }),
        ("Structured Entities", {
            "fields": ("pretty_entities",)
        }),
        ("Relationships", {
            "fields": ("pretty_relationships",)
        }),
        ("Search & Embeddings", {
            "fields": ("text_search", "embedding"),
            "classes": ("collapse",),  # collapsible UI section
        }),
    )

    # ------------------------
    # DISPLAY HELPERS
    # ------------------------
    def summary_snippet(self, obj):
        if not obj.summary:
            return ""
        return (obj.summary[:50] + "...") if len(obj.summary) > 50 else obj.summary
    summary_snippet.short_description = "Summary"

    def formatted_entities(self, obj):
        """One-line entity categories for quick overview."""
        if not obj.entities:
            return "-"
        keys = ", ".join(obj.entities.keys())
        return keys
    formatted_entities.short_description = "Entity Types"

    def pretty_entities(self, obj):
        """Pretty-print JSON."""
        if not obj.entities:
            return "-"
        return format_html(
            "<pre style='white-space:pre-wrap'>{}</pre>",
            json.dumps(obj.entities, indent=2)
        )
    pretty_entities.short_description = "Entities"

    def pretty_relationships(self, obj):
        if not obj.relationships:
            return "-"
        return format_html(
            "<pre style='white-space:pre-wrap'>{}</pre>",
            json.dumps(obj.relationships, indent=2)
        )
    pretty_relationships.short_description = "Relationships"

    # ------------------------
    # PERMISSIONS
    # ------------------------
    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True
