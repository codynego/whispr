# avatars/serializers/avatar.py
from rest_framework import serializers
from avatars.models import Avatar
from django.contrib.auth import get_user_model

User = get_user_model()


class AvatarListSerializer(serializers.ModelSerializer):
    """For listing avatars in dashboard"""
    url = serializers.SerializerMethodField()
    photo_url = serializers.ImageField(source="photo", read_only=True)
    is_trained = serializers.BooleanField(source="trained", read_only=True)
    total_conversations = serializers.IntegerField(read_only=True)

    class Meta:
        model = Avatar
        fields = [
            "id", "name", "handle", "photo_url", "purpose", "visibility",
            "is_trained", "total_conversations", "created_at", "url"
        ]

    def get_url(self, obj):
        request = self.context.get("request")
        if not request:
            return f"https://whisone.com/@{obj.handle}"
        return request.build_absolute_uri(f"/@{obj.handle}")


class AvatarDetailSerializer(serializers.ModelSerializer):
    """Full avatar details for owner"""
    photo_url = serializers.ImageField(source="photo", read_only=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True)
    training_in_progress = serializers.SerializerMethodField()

    class Meta:
        model = Avatar
        exclude = ["is_deleted", "deleted_at"]
        read_only_fields = [
            "trained", "trained_at", "total_conversations", "total_messages",
            "persona_prompt", "summary_knowledge", "writing_style"
        ]

    def get_training_in_progress(self, obj):
        return obj.training_jobs.filter(status__in=["queued", "running"]).exists()


class AvatarCreateSerializer(serializers.ModelSerializer):
    """Creating a new avatar"""
    class Meta:
        model = Avatar
        fields = ["name", "handle", "purpose", "tone_preset", "photo"]

    def validate_handle(self, value):
        if Avatar.objects.filter(handle=value, is_deleted=False).exists():
            raise serializers.ValidationError("This handle is already taken.")
        return value


class AvatarUpdateSerializer(serializers.ModelSerializer):
    """Partial updates (PUT/PATCH)"""
    handle = serializers.SlugField(read_only=True)  # can't change after creation

    class Meta:
        model = Avatar
        exclude = ["owner", "is_deleted", "deleted_at", "handle"]
        extra_kwargs = {
            field.name: {"required": False}
            for field in model._meta.fields
            if field.name not in ["id", "owner"]
        }


# avatars/serializers/conversation.py
from ..models import AvatarConversation, AvatarMessage
from rest_framework import serializers


class AvatarMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvatarMessage
        fields = ["id", "role", "content", "created_at"]
        read_only_fields = ["created_at"]


class AvatarConversationSerializer(serializers.ModelSerializer):
    messages = AvatarMessageSerializer(many=True, read_only=True)
    avatar_name = serializers.CharField(source="avatar.name", read_only=True)
    avatar_handle = serializers.CharField(source="avatar.handle", read_only=True)
    duration = serializers.SerializerMethodField()

    class Meta:
        model = AvatarConversation
        fields = [
            "id", "visitor_id", "visitor_name", "visitor_email",
            "started_at", "ended_at", "last_activity_at",
            "taken_over_by_owner", "lead_score", "converted",
            "avatar_name", "avatar_handle", "messages", "duration"
        ]

    def get_duration(self, obj):
        if not obj.ended_at:
            return None
        return (obj.ended_at - obj.started_at).seconds


# avatars/serializers/training.py
from avatars.models import AvatarTrainingJob


class AvatarTrainingJobSerializer(serializers.ModelSerializer):
    logs_preview = serializers.SerializerMethodField()

    class Meta:
        model = AvatarTrainingJob
        fields = ["id", "status", "started_at", "finished_at", "logs_preview"]

    def get_logs_preview(self, obj):
        if not obj.logs:
            return ""
        lines = obj.logs.strip().split("\n")[-10:]  # last 10 lines
        return "\n".join(lines)


class AvatarPublicSerializer(serializers.ModelSerializer):
    """What visitors see at https://whisone.com/@handle"""
    class Meta:
        model = Avatar
        fields = [
            "name", "handle", "photo", "welcome_message",
            "suggested_questions", "calendly_link",
            "collect_name", "collect_email"
        ]
        read_only_fields = fields