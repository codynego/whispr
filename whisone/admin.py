from django.contrib import admin
from .models import Note, Reminder, Todo, Integration, AutomationRule, DailySummary


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'summary_date', 'created_at')
    search_fields = ('user__username', 'summary_text')
    readonly_fields = ('created_at', 'raw_data')

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'content', 'created_at')
    search_fields = ('title', 'content', 'user__username')
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
from .models import Memory

@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "memory_type",
        "emotion",
        "sentiment",
        "importance",
        "summary_snippet",
        "created_at",
        "updated_at",
    )
    list_filter = ("memory_type", "emotion", "user", "created_at")
    search_fields = ("summary", "raw_text", "context")
    readonly_fields = ("embedding", "created_at", "updated_at")
    ordering = ("-created_at",)

    # Short snippet of summary for list display
    def summary_snippet(self, obj):
        return obj.summary[:50] + ("..." if len(obj.summary) > 50 else "")
    summary_snippet.short_description = "Summary"

    # Optional: collapsible context JSON
    fieldsets = (
        (None, {
            "fields": ("user", "memory_type", "raw_text", "summary", "emotion", "sentiment", "importance")
        }),
        ("Context & Embedding", {
            "fields": ("context", "embedding"),
            "classes": ("collapse",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )




from django.contrib import admin
from .models import UploadedFile

@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "original_filename",
        "file_type",
        "size",
        "processed",
        "uploaded_at",
    )
    list_filter = ("file_type", "processed", "uploaded_at")
    search_fields = ("original_filename", "user__email", "content")
    readonly_fields = ("uploaded_at", "size", "file_type", "original_filename")
    ordering = ("-uploaded_at",)

    # Optional: display a preview of content in admin
    def short_content(self, obj):
        if obj.content:
            return obj.content[:75] + "..." if len(obj.content) > 75 else obj.content
        return "-"
    short_content.short_description = "Content Preview"
