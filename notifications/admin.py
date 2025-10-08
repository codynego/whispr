from django.contrib import admin
from .models import Notification, NotificationPreference


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_notifications', 'push_notifications', 
                    'sms_notifications', 'whatsapp_notifications', 
                    'daily_summary', 'created_at')
    list_filter = ('email_notifications', 'push_notifications', 
                   'sms_notifications', 'whatsapp_notifications', 
                   'daily_summary')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'type', 'is_read', 'created_at', 'read_at')
    list_filter = ('type', 'is_read')
    search_fields = ('title', 'message', 'user__email')
    readonly_fields = ('created_at', 'read_at')
