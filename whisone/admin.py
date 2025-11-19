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
from .models import KnowledgeVaultEntry


@admin.register(KnowledgeVaultEntry)
class KnowledgeVaultEntryAdmin(admin.ModelAdmin):
    list_display = (
        "memory_id",
        "user",
        "summary_snippet",
        "timestamp",
        "last_accessed",
    )
    list_filter = ("timestamp", "last_accessed", "user")
    search_fields = ("memory_id", "user__username", "summary")
    readonly_fields = ("memory_id", "timestamp", "last_accessed")

    def summary_snippet(self, obj):
        """Shorten long summaries in list display."""
        return (obj.summary[:75] + "...") if obj.summary and len(obj.summary) > 75 else obj.summary
    summary_snippet.short_description = "Summary"

    def has_add_permission(self, request):
        """Optional: prevent manual creation from admin if desired."""
        return True  # Set False if you want to prevent manual additions

    def has_change_permission(self, request, obj=None):
        """Optional: allow edits only if needed."""
        return True

    def has_delete_permission(self, request, obj=None):
        """Optional: allow deletions."""
        return True
