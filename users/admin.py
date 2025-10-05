from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'whatsapp', 'plan', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'plan')
    search_fields = ('email', 'whatsapp', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'whatsapp')}),
        ('Subscription', {'fields': ('plan',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        ('Email Tokens', {'fields': ('gmail_refresh_token', 'outlook_refresh_token')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'whatsapp', 'plan'),
        }),
    )

