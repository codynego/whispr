# whisone/avatars/serializers.py
from rest_framework import serializers
from .models import (
    Avatar,
    AvatarSource,
    AvatarTrainingJob,
    AvatarMemoryChunk,
    AvatarConversation,
    AvatarMessage,
    AvatarAnalytics,
    AvatarSettings,
)

# ----------------------------
# Sub-Serializers (Used for nesting)
# ----------------------------

class AvatarSettingsSerializer(serializers.ModelSerializer):
    """Used for nested display in AvatarSerializer and the dedicated settings endpoint."""
    class Meta:
        model = AvatarSettings
        fields = [
            "is_public", # Renamed 'visibility' to 'is_public' for UI clarity
            "disclaimer_text", # Renamed/mapped from 'protected_code' or added new field
            "response_delay_ms", # Renamed 'async_delay_seconds' to ms for UI
            "enable_owner_takeover", # Renamed 'allow_owner_takeover' for UI
        ]
        
    # Mapping for fields based on models provided in the prompt's AvatarSettings
    is_public = serializers.BooleanField(source='visibility')
    response_delay_ms = serializers.IntegerField(source='async_delay_seconds')
    enable_owner_takeover = serializers.BooleanField(source='allow_owner_takeover')
    disclaimer_text = serializers.CharField(source='protected_code') # Using protected_code as a placeholder for disclaimer_text

class AvatarAnalyticsSerializer(serializers.ModelSerializer):
    """Used for nested display in AvatarSerializer and the dedicated analytics endpoint."""
    class Meta:
        model = AvatarAnalytics
        fields = [
            "visitors_count",
            "total_conversations",
            "total_messages",
            "average_response_time_ms", # New conceptual field for the UI display
        ]
    average_response_time_ms = serializers.SerializerMethodField()
    
    def get_average_response_time_ms(self, obj):
        # Placeholder for actual calculation logic in the model
        return 1200 # Default/placeholder value


# ----------------------------
# Core Models
# ----------------------------

class AvatarSerializer(serializers.ModelSerializer):
    settings = AvatarSettingsSerializer(read_only=True) # Nested Settings
    analytics = AvatarAnalyticsSerializer(read_only=True) # Nested Analytics

    class Meta:
        model = Avatar
        fields = [
            "id", "owner", "name", "handle", "photo", "tone", "persona_prompt",
            "trained", "trained_at", "created_at", "updated_at",
            "last_training_job_id", # Added for UI Monitoring initialization
            "settings", "analytics", # Nested Fields
        ]
        read_only_fields = ["owner", "trained", "trained_at", "created_at", "updated_at", "settings", "analytics"]
        
    # Helper to get the last job ID (assuming this field exists on the Avatar model)
    last_training_job_id = serializers.SerializerMethodField()
    def get_last_training_job_id(self, obj):
        last_job = obj.avatartrainingjob_set.order_by('-started_at').first()
        return str(last_job.id) if last_job else None


class AvatarConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarConversation
        fields = [
            "id", "avatar", "visitor_id", "started_at", "ended_at", "taken_over_by_owner",
        ]
        read_only_fields = ["started_at", "ended_at"]


class AvatarMessageSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S.%fZ", read_only=True) # Added format for UI
    class Meta:
        model = AvatarMessage
        fields = [
            "id", "conversation", "role", "content", "created_at",
        ]
        read_only_fields = ["created_at"]


# ----------------------------
# Optional / Advanced Models
# ----------------------------

class AvatarSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarSource
        fields = [
            "id", "avatar", "source_type", "metadata", "include_for_tone", 
            "include_for_knowledge", "enabled", "created_at",
        ]
        read_only_fields = ["created_at"]


class AvatarTrainingJobSerializer(serializers.ModelSerializer):
    progress = serializers.IntegerField(default=0) # Added progress field for UI monitor

    class Meta:
        model = AvatarTrainingJob
        fields = [
            "id", "avatar", "status", "progress", "logs", "started_at", "finished_at",
        ]
        read_only_fields = ["logs", "started_at", "finished_at"]


class AvatarMemoryChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarMemoryChunk
        fields = [
            "id", "avatar", "chunk_id", "text", "source_type", "embedding", "created_at",
        ]
        read_only_fields = ["chunk_id", "created_at"]

# AvatarAnalyticsSerializer and AvatarSettingsSerializer are defined above for clarity.