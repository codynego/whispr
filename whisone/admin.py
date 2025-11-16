from django.contrib import admin
from .models import Note, Reminder, Todo, Integration, AutomationRule

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
from .models import KnowledgeVaultEntry, UserPreference
import json
from django.utils.html import format_html

@admin.register(KnowledgeVaultEntry)
class KnowledgeVaultEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "memory_id", "summary_snippet", "timestamp", "last_accessed")
    search_fields = ("memory_id", "summary", "user__username", "user__email")
    list_filter = ("timestamp", "last_accessed", "user")
    readonly_fields = ("timestamp", "last_accessed")

    def summary_snippet(self, obj):
        """Show a short snippet of the summary"""
        return (obj.summary[:75] + "...") if obj.summary else "-"
    summary_snippet.short_description = "Summary"

    def entities_json(self, obj):
        """Pretty-print JSON for entities"""
        return format_html("<pre>{}</pre>", json.dumps(obj.entities, indent=2))
    entities_json.short_description = "Entities"

    def preferences_json(self, obj):
        """Pretty-print JSON for preferences"""
        return format_html("<pre>{}</pre>", json.dumps(obj.preferences, indent=2))
    preferences_json.short_description = "Preferences"

@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "preferences_snippet", "last_updated")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("last_updated",)

    def preferences_snippet(self, obj):
        """Show a short snippet of the preferences JSON"""
        prefs_str = json.dumps(obj.preferences, indent=2)
        return format_html("<pre>{}</pre>", prefs_str)
    preferences_snippet.short_description = "Preferences"
