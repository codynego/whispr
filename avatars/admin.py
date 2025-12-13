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
    list_display = ("name", "handle", "owner","description", "trained", "trained_at", "created_at")
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
            "fields": ("owner", "name", "handle", "photo", "description"),
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

from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import AvatarConversation
from django.utils import timezone


@admin.register(AvatarConversation)
class AvatarConversationAdmin(admin.ModelAdmin):
    """
    Admin configuration for the AvatarConversation model.
    """
    
    # Fields to display in the list view
    list_display = (
        'id', 
        'avatar', 
        'get_user_identifier', 
        'started_at', 
        'ended_at', 
        'duration',
        'taken_over_by_owner',
        'prompted_login',
    )
    
    # Fields to use as filters on the right sidebar
    list_filter = (
        'avatar',
        'taken_over_by_owner',
        'prompted_login',
        'started_at',
        'ended_at',
        'user__is_staff', # Example of filtering by user properties
    )

    # Fields that can be searched
    search_fields = (
        'id',
        'visitor_id',
        'user__email', # Search by the user's email
        'user__username', # Search by the user's username (if applicable)
    )

    # Fields to make read-only in the detail view
    readonly_fields = (
        'id', 
        'started_at', 
        'duration',
    )
    
    # Grouping and ordering of fields in the detail view
    fieldsets = (
        (None, {
            'fields': ('id', 'avatar', 'started_at', 'ended_at', 'duration')
        }),
        ('User Information', {
            'fields': ('user', 'visitor_id', 'prompted_login')
        }),
        ('Status', {
            'fields': ('taken_over_by_owner',)
        }),
    )
    
    # inlines = [AvatarMessageInline] # Uncomment if you have the Message model and inline configured

    # Custom method to display the user/visitor identifier
    @admin.display(description='User/Visitor')
    def get_user_identifier(self, obj):
        if obj.user:
            return mark_safe(f"**User:** {obj.user.email}")
        if obj.visitor_id:
            # Shorten visitor ID for display if it's very long
            display_id = obj.visitor_id[:8] + '...' if len(obj.visitor_id) > 10 else obj.visitor_id
            return mark_safe(f"Visitor: {display_id}")
        return "N/A"
    
    # Custom method to calculate conversation duration
    @admin.display(description='Duration')
    def duration(self, obj):
        if obj.ended_at:
            duration = obj.ended_at - obj.started_at
        elif obj.started_at:
            # Calculate duration up to the current moment if not ended
            duration = timezone.now() - obj.started_at
        else:
            return 'N/A'

        # Format duration nicely
        total_seconds = int(duration.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds:
            parts.append(f"{seconds}s")
            
        return " ".join(parts) if parts else "0s"

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
    list_display = ("avatar", "response_delay_ms", "visibility", "created_at") 
    search_fields = ("avatar__name",)
    readonly_fields = ("created_at", "updated_at")


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