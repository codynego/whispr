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



# admin.py
import uuid
from django.contrib import admin
from django.utils.html import format_html
from .models import Entity, Fact, Relationship


def short_uuid(value: uuid.UUID) -> str:
    """Return first 8 characters of UUID for cleaner display."""
    return str(value)[:8]


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'user', 'type', 'name', 'created_at')
    list_filter = ('type', 'created_at', 'user')
    search_fields = ('id', 'name', 'type', 'user__username', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    inlines = []  # We'll add FactInline below

    def short_id(self, obj):
        return short_uuid(obj.id)
    short_id.short_description = 'ID'
    short_id.admin_order_field = 'id'


class FactInline(admin.TabularInline):
    model = Fact
    extra = 1
    fields = ('key', 'value', 'confidence', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    can_delete = True
    show_change_link = True


# Add the inline to EntityAdmin
EntityAdmin.inlines = [FactInline]


@admin.register(Fact)
class FactAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'entity_link', 'key', 'truncated_value', 'confidence', 'created_at')
    list_filter = ('key', 'confidence', 'created_at')
    search_fields = ('key', 'value', 'entity__name', 'entity__id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)

    def short_id(self, obj):
        return short_uuid(obj.id)
    short_id.short_description = 'ID'

    def entity_link(self, obj):
        if not obj.entity:
            return "-"
        url = f"/admin/yourappname/entity/{obj.entity.id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.entity)
    entity_link.short_description = 'Entity'
    entity_link.admin_order_field = 'entity__name'

    def truncated_value(self, obj):
        max_length = 80
        value = obj.value or ""
        return value[:max_length] + ("..." if len(value) > max_length else "")
    truncated_value.short_description = 'Value'


@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = (
        'short_id',
        'user',
        'source_entity',
        'relation_type',
        'arrow',
        'target_entity',
        'created_at'
    )
    list_filter = ('relation_type', 'created_at', 'user')
    search_fields = (
        'source__name',
        'source__id',
        'target__name',
        'target__id',
        'relation_type',
        'user__username'
    )
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)

    def short_id(self, obj):
        return short_uuid(obj.id)
    short_id.short_description = 'ID'

    def source_entity(self, obj):
        return format_html(
            '<strong>{}</strong> <small style="color:#666">({})</small>',
            obj.source.name or f"[{obj.source.type}]",
            obj.source.type
        ) if obj.source else "-"
    source_entity.short_description = 'From'
    source_entity.admin_order_field = 'source__name'

    def target_entity(self, obj):
        return format_html(
            '<strong>{}</strong> <small style="color:#666">({})</small>',
            obj.target.name or f"[{obj.target.type}]",
            obj.target.type
        ) if obj.target else "-"
    target_entity.short_description = 'To'
    target_entity.admin_order_field = 'target__name'

    def arrow(self, obj):
        return "→"
    arrow.short_description = ''