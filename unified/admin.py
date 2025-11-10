from django.contrib import admin
from .models import ChannelAccount, Conversation, Message, UserRule, CalendarEvent



@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    """
    Admin interface for CalendarEvent model.
    """
    list_display = ['summary', 'start_time', 'end_time', 'status', 'account', 'organizer']
    list_filter = ['status', 'account', 'start_time', 'all_day', 'created_at']
    search_fields = ['summary', 'description', 'organizer', 'external_id']
    readonly_fields = ['external_id', 'i_cal_uid', 'html_link', 'created_at', 'updated_at']
    date_hierarchy = 'start_time'
    fieldsets = (
        ('Event Basics', {
            'fields': ('account', 'conversation', 'summary', 'description', 'status')
        }),
        ('Timing & Location', {
            'fields': ('start_time', 'end_time', 'location', 'all_day')
        }),
        ('Attendees & Organizer', {
            'fields': ('attendees', 'organizer')
        }),
        ('External Links', {
            'fields': ('external_id', 'html_link', 'i_cal_uid'),
            'classes': ('collapse',)  # Collapsible for less clutter
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    filter_horizontal = ['attendees']  # If attendees were a M2M; JSONField so skip

    def get_queryset(self, request):
        """Optimize queryset for performance."""
        qs = super().get_queryset(request)
        return qs.select_related('account', 'conversation').prefetch_related('attendees')

    def get_readonly_fields(self, request, obj=None):
        """Make more fields readonly in production."""
        readonly = list(self.readonly_fields)
        if obj:  # Editing existing
            readonly.extend(['start_time', 'end_time', 'status'])  # Prevent changes post-sync
        return readonly


@admin.register(ChannelAccount)
class ChannelAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "channel", "provider", "address_or_id", "is_active", "last_synced")
    list_filter = ("channel", "provider", "is_active")
    search_fields = ("address_or_id", "user__email", "provider")
    readonly_fields = ("created_at", "updated_at", "last_synced")
    ordering = ("-updated_at",)


class MessageInline(admin.TabularInline):
    model = Message
    fields = ("sender", "content", "sent_at", "is_read", "importance")
    readonly_fields = ("sender", "content", "sent_at")
    extra = 0
    show_change_link = True


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "account", "channel", "last_sender", "last_message_at", "is_archived")
    list_filter = ("channel", "is_archived")
    search_fields = ("title", "last_sender", "thread_id")
    readonly_fields = ("created_at", "updated_at", "last_message_at")
    inlines = [MessageInline]
    ordering = ("-last_message_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "channel",
        "sender",
        "account",
        "sent_at",
        "importance",
        "is_read",
        "is_starred",
        "is_incoming",
    )
    list_filter = ("channel", "importance", "is_read", "is_incoming")
    search_fields = ("sender", "content", "external_id", "conversation__title")
    readonly_fields = ("created_at", "updated_at", "embedding")
    ordering = ("-sent_at",)


@admin.register(UserRule)
class UserRuleAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "rule_type", "channel", "importance", "is_active")
    list_filter = ("rule_type", "channel", "importance", "is_active")
    search_fields = ("name", "value", "user__email")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
