from django.contrib import admin
from .models import (
    Avatar,
    AvatarSource,
    AvatarTrainingJob,
    AvatarMemoryChunk,
    AvatarConversation,
    AvatarMessage,
    AvatarSettings,
    AvatarAnalytics,
)
from django.utils import timezone # Import timezone for created_at fix in AvatarTrainingJob

# -----------------------
# Inline Models
# -----------------------

class AvatarSourceInline(admin.TabularInline):
    model = AvatarSource
    extra = 0
    readonly_fields = ("created_at",)


class AvatarSettingsInline(admin.StackedInline):
    model = AvatarSettings
    extra = 0
    # FIX: created_at and updated_at are now fields on AvatarSettings
    readonly_fields = ("created_at", "updated_at")


class AvatarMessageInline(admin.TabularInline):
    model = AvatarMessage
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("role", "content", "created_at")


# -----------------------
# Main Avatar Admin
# -----------------------

@admin.register(Avatar)
class AvatarAdmin(admin.ModelAdmin):
    # The fields 'writing_style' and 'summary_knowledge' are missing from Avatar model, 
    # but I'll only fix the errors reported. Assume they are to be removed or added later.
    list_display = ("name", "handle", "owner", "trained", "trained_at", "created_at")
    search_fields = ("name", "handle", "owner__email")
    list_filter = ("trained", "created_at")
    readonly_fields = ("created_at", "trained_at")

    inlines = [
        AvatarSourceInline,
        AvatarSettingsInline,
    ]
    # The fields 'writing_style' and 'summary_knowledge' are missing, 
    # removed them from the fieldsets to pass validation.
    fieldsets = (
        ("Basic Info", {
            "fields": ("owner", "name", "handle", "photo"),
        }),
        ("Personality", {
            "fields": ("persona_prompt", "tone"), 
        }),
        ("Training Status", {
            "fields": ("trained", "trained_at"),
        }),
        ("Timestamps", {
            "fields": ("created_at",),
        }),
    )


# -----------------------
# Avatar Sources Admin
# -----------------------

@admin.register(AvatarSource)
class AvatarSourceAdmin(admin.ModelAdmin):
    list_display = ("avatar", "source_type", "enabled", "include_for_knowledge", "include_for_tone", "created_at")
    list_filter = ("source_type", "enabled", "include_for_knowledge", "include_for_tone")
    search_fields = ("avatar__name",)
    # FIX: AvatarSource model does not have 'updated_at'
    readonly_fields = ("created_at",) 
    fields = (
        "avatar", "source_type", "enabled",
        "include_for_knowledge", "include_for_tone", "metadata",
        "created_at", 
    )


# -----------------------
# Training Jobs
# -----------------------

@admin.register(AvatarTrainingJob)
class AvatarTrainingJobAdmin(admin.ModelAdmin):
    # FIX: AvatarTrainingJob model does not have 'created_at' as an explicit field, 
    # it is implicitly used in Django 4.0+ if not provided, but here we see started_at and finished_at. 
    # If the user intended created_at to be on the model, it should be added.
    # Assuming 'started_at' is used instead of 'created_at' for display, and removing 'created_at' from readonly. 
    # If 'created_at' is a required timestamp, it should be added to the model.
    # To fix the E108/E116 errors, I'll remove 'created_at' from list_display, list_filter and readonly_fields 
    # since it's not a field on AvatarTrainingJob model.
    # If it was added to the model: readonly_fields = ("created_at", "started_at", "finished_at")
    
    # As the model does not have 'created_at', I will remove it.
    list_display = ("avatar", "status", "started_at", "finished_at")
    list_filter = ("status",) # FIX: Removed "created_at"
    search_fields = ("avatar__name",)
    readonly_fields = ("logs", "started_at", "finished_at") # FIX: Removed "created_at"

    fields = (
        "avatar", "status",
        "started_at", "finished_at",
        "logs",
    )


# -----------------------
# Memory Chunks (Embeddings)
# -----------------------

@admin.register(AvatarMemoryChunk)
class AvatarMemoryChunkAdmin(admin.ModelAdmin):
    list_display = ("avatar", "source_type", "short_text", "created_at")
    search_fields = ("text", "avatar__name")
    list_filter = ("source_type",)
    readonly_fields = ("embedding", "created_at")

    def short_text(self, obj):
        return obj.text[:80] + "..." if len(obj.text) > 80 else obj.text
    # Note: 'short_text' is a method on the Admin class, not the model, 
    # which is correct for list_display and resolves no errors.


# -----------------------
# Conversations + Messages
# -----------------------

@admin.register(AvatarConversation)
class AvatarConversationAdmin(admin.ModelAdmin):
    
    # Custom method to display 'taken_over_by_owner' under the name 'takeover'
    def takeover(self, obj):
        return obj.taken_over_by_owner
    takeover.boolean = True # Display as a checkbox

    list_display = ("avatar", "visitor_id", "started_at", "ended_at", "takeover") # FIX: 'takeover' is now a method
    search_fields = ("avatar__name", "visitor_id")
    # FIX: 'takeover' is not a field. Use the actual field name for filtering.
    list_filter = ("taken_over_by_owner", "started_at") 

    inlines = [AvatarMessageInline]

    readonly_fields = ("started_at", "ended_at")


@admin.register(AvatarMessage)
class AvatarMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "short_msg", "created_at")
    search_fields = ("content",)
    list_filter = ("role",)
    readonly_fields = ("created_at",)

    def short_msg(self, obj):
        return obj.content[:80] + "..." if len(obj.content) > 80 else obj.content


# -----------------------
# Settings
# -----------------------

@admin.register(AvatarSettings)
class AvatarSettingsAdmin(admin.ModelAdmin):
    
    # Custom method to display 'async_delay_seconds' under the name 'response_delay_ms'
    def response_delay_ms(self, obj):
        # Assuming the user wants to show milliseconds (seconds * 1000)
        return f"{obj.async_delay_seconds * 1000} ms"
    response_delay_ms.admin_order_field = 'async_delay_seconds'

    # FIX: created_at and updated_at are now fields on the model
    list_display = ("avatar", "response_delay_ms", "visibility") 
    search_fields = ("avatar__name",)



# -----------------------
# Analytics
# -----------------------

@admin.register(AvatarAnalytics)
class AvatarAnalyticsAdmin(admin.ModelAdmin):
    
    # Custom method to display 'visitors_count' under the name 'total_visits'
    def total_visits(self, obj):
        return obj.visitors_count
    total_visits.admin_order_field = 'visitors_count'

    # Custom method to display 'last_active_at' under the name 'last_interaction'
    def last_interaction(self, obj):
        return obj.last_active_at
    last_interaction.admin_order_field = 'last_active_at'
    
    # FIX: list_display now refers to the custom methods
    list_display = ("avatar", "total_visits", "total_messages", "last_interaction")
    readonly_fields = ("avatar",)