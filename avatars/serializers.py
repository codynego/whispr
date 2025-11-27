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
from django.db.models import Max # Required for some SerializerMethodFields

# ----------------------------
# Sub-Serializers (Used for nesting)
# ----------------------------

class AvatarSettingsSerializer(serializers.ModelSerializer):
    """
    Handles serialization for AvatarSettings. 
    Uses 'source' mapping for better UI field names.
    """
    # Renaming internal fields for UI clarity
    is_public = serializers.BooleanField(source='visibility')
    response_delay_ms = serializers.IntegerField(source='async_delay_seconds')
    enable_owner_takeover = serializers.BooleanField(source='allow_owner_takeover')
    disclaimer_text = serializers.CharField(source='protected_code') # Using protected_code as a placeholder for disclaimer_text

    class Meta:
        model = AvatarSettings
        fields = [
            # UI names
            "is_public", 
            "disclaimer_text", 
            "response_delay_ms", 
            "enable_owner_takeover", 
        ]
        # Allow updating all fields via the handle-based PUT/PATCH endpoint
        read_only_fields = ['avatar']


class AvatarAnalyticsSerializer(serializers.ModelSerializer):
    """
    Handles serialization for AvatarAnalytics. 
    Includes computed performance metrics.
    """
    average_response_time_ms = serializers.SerializerMethodField()
    
    class Meta:
        model = AvatarAnalytics
        fields = [
            "visitors_count",
            "total_conversations",
            "total_messages",
            "average_response_time_ms",
        ]
        read_only_fields = fields # All analytics data is read-only / system-generated
    
    def get_average_response_time_ms(self, obj):
        # Placeholder logic: Replace with actual calculation based on message timestamps
        return 1200


# ----------------------------
# Core Models
# ----------------------------

class AvatarSerializer(serializers.ModelSerializer):
    """
    Main Avatar serializer, nesting Settings and Analytics.
    """
    settings = AvatarSettingsSerializer(read_only=True) 
    analytics = AvatarAnalyticsSerializer(read_only=True) 
    last_training_job_id = serializers.SerializerMethodField()

    class Meta:
        model = Avatar
        fields = [
            "id", "owner", "name", "handle", "photo", "tone", "persona_prompt",
            "trained", "trained_at", "created_at", "updated_at",
            "last_training_job_id", 
            "settings", "analytics", 
        ]
        read_only_fields = ["owner", "trained", "trained_at", "created_at", "updated_at", "settings", "analytics"]
        
    def get_last_training_job_id(self, obj):
        """Retrieves the ID of the most recently started training job for monitoring."""
        # FIX APPLIED: Changed avatartrainingjob_set to the correct related_name 'training_jobs'
        last_job = obj.training_jobs.order_by('-started_at').first()
        return str(last_job.id) if last_job else None


class AvatarConversationSerializer(serializers.ModelSerializer):
    """Handles serialization for AvatarConversation."""
    class Meta:
        model = AvatarConversation
        fields = [
            "id", "avatar", "visitor_id", "started_at", "ended_at", "taken_over_by_owner",
        ]
        read_only_fields = ["started_at", "ended_at"]


class AvatarMessageSerializer(serializers.ModelSerializer):
    """Handles serialization for AvatarMessage."""
    # Use explicit format for UI timestamp consistency
    created_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S.%fZ", read_only=True) 
    
    class Meta:
        model = AvatarMessage
        fields = [
            "id", "conversation", "role", "content", "created_at",
        ]
        read_only_fields = ["created_at"]


# ----------------------------
# Optional / Advanced Models
# ----------------------------

# serializers.py (updated section only)

class AvatarSourceSerializer(serializers.ModelSerializer):
    """
    Serializer for AvatarSource – used in bulk replace-all endpoint:
    POST /api/avatars/{handle}/sources/

    Expected payload (array of objects):
    [
      {
        "source_type": "notes",
        "include_for_tone": true,
        "include_for_knowledge": true,
        "metadata": { "ids": [1, 2, 3] }   // optional, can be {} or omitted
      },
      ...
    ]

    Sending an empty array [] → means "remove all sources" (handled in view).
    """

    # Make metadata optional and always default to empty dict
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        allow_null=True,
        help_text="Extra config. For item-filtered sources, use { 'ids': [...] }",
    )

    class Meta:
        model = AvatarSource
        fields = [
            "id",
            "source_type",
            "metadata",
            "include_for_tone",
            "include_for_knowledge",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        # We let the view inject `avatar`, so it's not in input

    # ──────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────
    def validate_source_type(self, value: str) -> str:
        allowed = {"notes", "reminders", "todos", "uploads", "gmail", "website"}
        if value not in allowed:
            raise serializers.ValidationError(f"Invalid source_type. Allowed: {', '.join(allowed)}")
        return value

    def validate_metadata(self, value):
        """
        Ensure that when the source type supports item selection,
        metadata either is missing or contains an 'ids' list (can be empty).
        """
        source_type = self.initial_data.get("source_type")

        # Only certain sources use item filtering
        item_filtered_sources = {"notes", "reminders", "todos", "uploads"}

        if source_type in item_filtered_sources:
            if value is None:
                return {"ids": []}  # normalize to expected shape
            if not isinstance(value, dict):
                raise serializers.ValidationError("metadata must be a JSON object")
            if "ids" not in value:
                # Auto-fix common frontend mistake
                return {"ids": []}
            if not isinstance(value["ids"], list):
                raise serializers.ValidationError("'ids' in metadata must be a list")
            return value
        else:
            # For sources like gmail/website, just pass through
            return value or {}

    def validate(self, attrs):
        """
        Final safety net:
        - If source is disabled for both tone and knowledge → reject unless it's just clearing
        - But we allow it because frontend sends everything and we filter in view
        """
        tone = attrs.get("include_for_tone", False)
        knowledge = attrs.get("include_for_knowledge", False)

        # Allow completely disabled entries – they will be filtered out in the view
        # But if both are True, at least one must be enabled (doesn't make sense otherwise)
        if tone is False and knowledge is False:
            # This is fine – it means "don't use this source"
            pass

        return attrs

    # ──────────────────────────────────────────────────────────────
    # Representation (for GET /list)
    # ──────────────────────────────────────────────────────────────
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Ensure metadata is always a dict (never None) on output
        if ret["metadata"] is None:
            ret["metadata"] = {}
        # For item-filtered sources, guarantee "ids" key exists
        if instance.source_type in {"notes", "reminders", "todos", "uploads"}:
            ret["metadata"] = {"ids": ret["metadata"].get("ids", [])}
        return ret


class AvatarTrainingJobSerializer(serializers.ModelSerializer):
    """
    Handles serialization for AvatarTrainingJob.
    Includes a 'progress' field for UI monitoring.
    """
    progress = serializers.IntegerField(default=0) 

    class Meta:
        model = AvatarTrainingJob
        fields = [
            "id", "avatar", "status", "progress", "logs", "started_at", "finished_at",
        ]
        read_only_fields = ["logs", "started_at", "finished_at"]


class AvatarMemoryChunkSerializer(serializers.ModelSerializer):
    """Handles serialization for AvatarMemoryChunk (RAG data chunks)."""
    class Meta:
        model = AvatarMemoryChunk
        fields = [
            "id", "avatar", "chunk_id", "text", "source_type", "embedding", "created_at",
        ]
        read_only_fields = ["chunk_id", "created_at"]