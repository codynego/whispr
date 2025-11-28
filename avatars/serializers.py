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

# avatars/serializers.py



from rest_framework import serializers
from .models import AvatarSource

class AvatarSourceListSerializer(serializers.ListSerializer):
    """Handles bulk creation of AvatarSource instances."""
    def create(self, validated_data):
        print("\n--- AvatarSourceListSerializer.create START ---")
        print(f"Validated Data (Count): {len(validated_data)}")
        
        # We need the avatar instance, which is typically passed from the view
        # or accessed via self.context. We'll assume it's in context for now.
        avatar = self.context.get("avatar")
        print(f"Context Avatar: {avatar}")
        
        if not avatar:
            print("ERROR: Avatar context is missing!")
            raise serializers.ValidationError("Avatar context must be provided for bulk creation.")

        # Optional: Print the first few items to confirm structure
        if validated_data:
            print(f"First Validated Item: {validated_data[0]}")
            
        try:
            # Prepare instances for bulk creation
            sources = [
                AvatarSource(avatar=avatar, **item)
                for item in validated_data
            ]
            print(f"Prepared {len(sources)} AvatarSource instances for bulk_create.")
            
            # Perform the bulk creation
            result = AvatarSource.objects.bulk_create(sources)
            print("Bulk creation successful.")
            return result
        except Exception as e:
            print(f"!!! CRITICAL ERROR during bulk_create: {e}")
            raise e
        finally:
            print("--- AvatarSourceListSerializer.create END ---\n")


# The main serializer
class AvatarSourceSerializer(serializers.ModelSerializer):
    metadata = serializers.JSONField(default=dict)

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
        
        # Specify the list serializer to use for bulk operations
        list_serializer_class = AvatarSourceListSerializer 

    def validate(self, attrs):
        print(f"\n--- AvatarSourceSerializer.validate START (Type: {attrs.get('source_type', 'N/A')}) ---")
        
        # Your existing validation logic is fine
        tone = attrs.get("include_for_tone", False)
        knowledge = attrs.get("include_for_knowledge", False)
        
        print(f"Tone: {tone}, Knowledge: {knowledge}")
        
        if not tone and not knowledge and attrs.get("source_type"):
            print("Validation PASS: Source is included but flags are false (expected behavior if used for deletion).")
            pass 
        else:
            print("Validation PASS: Flags are set or source_type is missing.")
            
        print("--- AvatarSourceSerializer.validate END ---\n")
        return attrs

    def create(self, validated_data):
        # This method is only used if `many=False` is passed to the serializer.
        print("\n--- AvatarSourceSerializer.create (SINGLE ITEM) CALLED ---")
        print("This should generally NOT be called when using AvatarSourceListSerializer.")
        print(f"Validated Data: {validated_data}")
        return super().create(validated_data)


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