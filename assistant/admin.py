from django.contrib import admin
from .models import AssistantTask, AssistantConfig, AssistantMessage
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import Automation

User = get_user_model()



@admin.register(AssistantMessage)
class AssistantMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'content', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('user__email', 'content')
    readonly_fields = ('created_at',)


@admin.register(AssistantConfig)
class AssistantConfigAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'is_enabled',
        'default_model',
        'max_response_length',
        'temperature',
        'top_p',
        'tone',
        'updated_at',
    )
    list_filter = ('is_enabled', 'default_model', 'tone')
    search_fields = ('user__email', 'tone', 'default_model')
    readonly_fields = ('created_at', 'updated_at')


class IsDueFilter(admin.SimpleListFilter):
    """Custom filter for is_due property."""
    title = 'Is Due'
    parameter_name = 'is_due'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'yes':
            return queryset.filter(due_time__lte=now)
        elif self.value() == 'no':
            return queryset.filter(due_time__isnull=True) | queryset.filter(due_time__gt=now)
        return queryset

@admin.register(AssistantTask)
class AssistantTaskAdmin(admin.ModelAdmin):
    """Admin configuration for AssistantTask model."""
    
    list_display = (
        'task_type',
        'status',
        'user',
        'input_text_preview',
        'output_text_preview',
        'created_at',
        'is_due',
    )
    
    list_filter = (
        'task_type',
        'status',
        IsDueFilter,
        'is_recurring',
        'created_at',
    )
    
    search_fields = (
        'input_text',
        'output_text',
        'error_message',
        'user__username',
        'user__email',
    )
    
    readonly_fields = (
        'created_at',
        'updated_at',
        'completed_at',
        'processing_time',
    )
    
    fieldsets = (
        ('Task Details', {
            'fields': ('task_type', 'status', 'input_text', 'context')
        }),
        ('Output & Errors', {
            'fields': ('output_text', 'error_message', 'processing_time')
        }),
        ('Email Relation', {
            'fields': ('related_email_id',),
            'classes': ('collapse',)
        }),
        ('Scheduling', {
            'fields': ('due_datetime', 'is_recurring', 'recurrence_pattern'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def input_text_preview(self, obj):
        """Preview of input text, truncated."""
        return obj.input_text[:50] + '...' if len(obj.input_text) > 50 else obj.input_text
    input_text_preview.short_description = 'Input Preview'
    
    def output_text_preview(self, obj):
        """Preview of output text, truncated."""
        return obj.output_text[:50] + '...' if len(obj.output_text) > 50 else obj.output_text
    output_text_preview.short_description = 'Output Preview'
    
    def get_queryset(self, request):
        """Optimize queryset for list view."""
        qs = super().get_queryset(request)
        qs = qs.select_related('user')
        return qs




@admin.register(Automation)
class AutomationAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Automation model.
    """
    list_display = (
        'name',
        'user',
        'trigger_type',
        'action_type',
        'is_active',
        'last_triggered_at',
        'next_run_at',
    )
    list_filter = (
        'trigger_type',
        'action_type',
        'is_active',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'name',
        'description',
        'user__username',  # Assuming AUTH_USER_MODEL has username field
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_triggered_at',
    )
    fieldsets = (
        (_('Core'), {
            'fields': (
                'user',
                'name',
                'description',
            )
        }),
        (_('Trigger'), {
            'fields': (
                'trigger_type',
                'trigger_condition',
            )
        }),
        (_('Action'), {
            'fields': (
                'action_type',
                'action_params',
            )
        }),
        (_('Schedule'), {
            'fields': (
                'is_active',
                'next_run_at',
                'recurrence_pattern',
            )
        }),
        (_('Metadata'), {
            'fields': (
                'created_at',
                'updated_at',
                'last_triggered_at',
            ),
            'classes': ('collapse',),
        }),
    )
    filter_horizontal = ()  # No m2m fields here, but add if needed in future
    ordering = ('-created_at',)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj:  # For existing objects
            readonly_fields.extend(['user', 'trigger_type', 'action_type'])
        return tuple(readonly_fields)