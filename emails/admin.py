from django.contrib import admin
from .models import EmailAccount, Email


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = ('email_address', 'provider', 'user', 'is_active', 'last_synced', 'created_at')
    list_filter = ('provider', 'is_active')
    search_fields = ('email_address', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'recipient', 'importance', 'is_read', 'received_at')
    list_filter = ('importance', 'is_read', 'is_starred')
    search_fields = ('subject', 'sender', 'recipient', 'body')
    readonly_fields = ('message_id', 'created_at', 'updated_at', 'analyzed_at')
    date_hierarchy = 'received_at'
