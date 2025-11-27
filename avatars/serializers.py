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
# Core Models
# ----------------------------

class AvatarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Avatar
        fields = [
            "id",
            "owner",
            "name",
            "handle",
            "photo",
            "tone",
            "persona_prompt",
            "trained",
            "trained_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["owner", "trained", "trained_at", "created_at", "updated_at"]


class AvatarConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarConversation
        fields = [
            "id",
            "avatar",
            "visitor_id",
            "started_at",
            "ended_at",
            "taken_over_by_owner",
        ]
        read_only_fields = ["started_at", "ended_at"]


class AvatarMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarMessage
        fields = [
            "id",
            "conversation",
            "role",
            "content",
            "created_at",
        ]
        read_only_fields = ["created_at"]


# ----------------------------
# Optional / Advanced Models
# ----------------------------

class AvatarSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarSource
        fields = [
            "id",
            "avatar",
            "source_type",
            "metadata",
            "include_for_tone",
            "include_for_knowledge",
            "enabled",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class AvatarTrainingJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarTrainingJob
        fields = [
            "id",
            "avatar",
            "status",
            "logs",
            "started_at",
            "finished_at",
        ]
        read_only_fields = ["logs", "started_at", "finished_at"]


class AvatarMemoryChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarMemoryChunk
        fields = [
            "id",
            "avatar",
            "chunk_id",
            "text",
            "source_type",
            "embedding",
            "created_at",
        ]
        read_only_fields = ["chunk_id", "created_at"]


class AvatarAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarAnalytics
        fields = [
            "id",
            "avatar",
            "visitors_count",
            "total_conversations",
            "total_messages",
            "last_active_at",
        ]
        read_only_fields = ["last_active_at"]


class AvatarSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarSettings
        fields = [
            "avatar",
            "async_delay_seconds",
            "visibility",
            "protected_code",
            "allow_owner_takeover",
        ]
