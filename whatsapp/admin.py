from django.contrib import admin
from .models import WhatsAppMessage, WhatsAppWebhook


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ('to_number', 'user', 'status', 'alert_type', 'created_at', 'sent_at')
    list_filter = ('status', 'alert_type')
    search_fields = ('to_number', 'message', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'sent_at')


@admin.register(WhatsAppWebhook)
class WhatsAppWebhookAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'processed', 'created_at')
    list_filter = ('event_type', 'processed')
    readonly_fields = ('created_at',)
