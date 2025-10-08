from django.contrib import admin
from .models import AssistantTask, AssistantConfig

@admin.register(AssistantConfig)
class AssistantConfigAdmin(admin.ModelAdmin):
    


@admin.register(AssistantTask)
class AssistantTaskAdmin(admin.ModelAdmin):
    list_display = ('task_type', 'user', 'status', 'processing_time', 'created_at', 'completed_at')
    list_filter = ('task_type', 'status')
    search_fields = ('user__email', 'input_text', 'output_text')
    readonly_fields = ('created_at', 'updated_at', 'completed_at', 'processing_time')
