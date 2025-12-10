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

from rest_framework import serializers

class AvatarSettingsSerializer(serializers.ModelSerializer):
    """
    Handles serialization for AvatarSettings with full read/write type casting 
    for the 'is_public' <-> 'visibility' field.
    """
    
    # Define 'is_public' as a BooleanField without a source. 
    # Its logic will be handled manually in to_internal_value and get_is_public.
    is_public = serializers.SerializerMethodField()
    
    # These fields correctly use 'source' for automatic mapping
    response_delay_ms = serializers.IntegerField(source='async_delay_seconds')
    enable_owner_takeover = serializers.BooleanField(source='allow_owner_takeover')
    disclaimer_text = serializers.CharField(source='protected_code', allow_null=True)

    class Meta:
        model = AvatarSettings
        fields = [
            "is_public", 
            "disclaimer_text", 
            "response_delay_ms", 
            "enable_owner_takeover", 
        ]
        # We must include the actual model field 'visibility' here to allow it to be 
        # saved, but we'll exclude it from the final output/input validation flow.
        extra_kwargs = {'visibility': {'write_only': True}} # Ensure visibility is not shown on GET
        
    # --- Custom Read Method (Model String -> JSON Boolean) ---
    def get_is_public(self, obj):
        """Converts model's visibility choice ('public', 'protected', 'private') to a boolean for GET requests."""
        # Only 'public' should return True for 'is_public'.
        return obj.visibility == 'public'

    # --- Custom Write Method (JSON Payload -> Model Field Data) ---
    def to_internal_value(self, data):
        """Translates the 'is_public' boolean from the payload into the model's 'visibility' string choice."""
        
        # 1. Manually handle 'is_public' since it's a SerializerMethodField for reading
        #    but we want to use the key for writing.
        if 'is_public' in data:
            is_public_value = data.pop('is_public') 
            
            # Map the boolean to the string choice your model expects
            if is_public_value is True:
                visibility_choice = 'public'
            elif is_public_value is False:
                # Assuming False maps to 'private'. If you want it to default to 'protected' 
                # when not 'public', adjust this logic.
                visibility_choice = 'private'
            else:
                 visibility_choice = None # or raise ValidationError

            if visibility_choice is not None:
                data['visibility'] = visibility_choice
        return super().to_internal_value(data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)


from rest_framework import serializers
from avatars.models import AvatarAnalytics, AvatarConversation, AvatarMessage

class AvatarAnalyticsSerializer(serializers.ModelSerializer):
    """
    Handles serialization for AvatarAnalytics. 
    Includes computed performance metrics.
    """
    average_response_time_ms = serializers.SerializerMethodField()
    # total_conversations = serializers.SerializerMethodField()
    # total_messages = serializers.SerializerMethodField()
    
    class Meta:
        model = AvatarAnalytics
        fields = [
            "visitors_count",
            "total_conversations",
            "total_messages",
            "average_response_time_ms",
        ]
        read_only_fields = fields  # All analytics data is read-only / system-generated
    
    def get_average_response_time_ms(self, obj):
        return 1200


from rest_framework import serializers
from avatars.models import Avatar, AvatarConversation, AvatarMessage

class AvatarSerializer(serializers.ModelSerializer):
    """
    Main Avatar serializer, nesting Settings and Analytics, with conversation and message counts.
    """
    settings = AvatarSettingsSerializer(read_only=True) 
    analytics = AvatarAnalyticsSerializer(read_only=True) 
    last_training_job_id = serializers.SerializerMethodField()
    
    # NEW: Conversation and Message counts
    conversations_count = serializers.SerializerMethodField()
    messages_count = serializers.SerializerMethodField()

    class Meta:
        model = Avatar
        fields = [
            "id", "owner", "name", "handle", "photo", "tone", "persona_prompt",
            "trained", "trained_at", "created_at", "updated_at",
      
            "settings", "analytics",
            "conversations_count", "messages_count", "last_training_job_id",
        ]
        read_only_fields = [
            "owner", "trained", "trained_at", "created_at", "updated_at", 
            "settings", "analytics", "conversations_count", "messages_count", "last_training_job_id"
        ]

    def get_last_training_job_id(self, obj):
        # This works even with UUID primary keys
        latest_job = obj.training_jobs.order_by('-finished_at').values('id').first()
        return latest_job['id'] if latest_job else None

    def get_conversations_count(self, obj):
        return AvatarConversation.objects.filter(avatar=obj).count()

    def get_messages_count(self, obj):
        return AvatarMessage.objects.filter(conversation__avatar=obj).count()


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
    
    # Explicitly define the boolean fields with default=True and required=False
    include_for_tone = serializers.BooleanField(
        default=True,
        required=False,
        allow_null=True  # Optional: allows null if sent explicitly
    )
    include_for_knowledge = serializers.BooleanField(
        default=True,
        required=False,
        allow_null=True
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
        read_only_fields = ["id", "created_at", "include_for_tone", "include_for_knowledge"]
        list_serializer_class = AvatarSourceListSerializer

    def validate(self, attrs):
        print(f"\n--- AvatarSourceSerializer.validate START (Type: {attrs.get('source_type', 'N/A')}) ---")
        
        tone = attrs.get("include_for_tone", True)       # Safe fallback
        knowledge = attrs.get("include_for_knowledge", True)  # Safe fallback
        
        print(f"Tone: {tone}, Knowledge: {knowledge}")
        
        # Optional: you can still allow both false only if it's intended for deletion or cleanup
        if not tone and not knowledge:
            source_type = attrs.get("source_type")
            if source_type is not None:
                print("WARNING: Both flags are False but source_type is present. Allowing only if intended for exclusion.")
            else:
                print("Both flags False and no source_type — likely deletion/soft-disable.")
        
        print("--- AvatarSourceSerializer.validate END ---\n")
        return attrs

    def create(self, validated_data):
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