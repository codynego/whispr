from django.contrib import admin
from .models import AssistantTask, AssistantConfig, AssistantMessage


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




@admin.register(AssistantTask)
class AssistantTaskAdmin(admin.ModelAdmin):
    list_display = ('task_type', 'user', 'status', 'processing_time', 'created_at', 'completed_at')
    list_filter = ('task_type', 'status')
    search_fields = ('user__email', 'input_text', 'output_text')
    readonly_fields = ('created_at', 'updated_at', 'completed_at', 'processing_time')
