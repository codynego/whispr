from django.contrib import admin
from .models import ChannelAccount, Conversation, Message, UserRule


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
