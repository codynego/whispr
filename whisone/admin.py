from django.contrib import admin
from .models import Note, Reminder, Todo

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


# whisone/admin.py

from django.contrib import admin
from .models import AutomationRule

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
