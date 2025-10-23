from rest_framework import serializers
from .models import AssistantTask, AssistantConfig, AssistantMessage


class AssistantMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantMessage
        fields = ['id', 'role', 'content', 'created_at']



class AssistantConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssistantConfig
        fields = [
            'id',
            'is_enabled',
            'default_model',
            'max_response_length',
            'temperature',
            'top_p',
            'tone',
            'custom_instructions',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AssistantTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for assistant tasks (email send, reminders, replies, etc.)
    """

    class Meta:
        model = AssistantTask
        fields = [
            "id",
            "user",
            "task_type",
            "status",
            "input_text",
            "context",
            "output_text",
            "error_message",
            "related_email_id",
            "processing_time",
            "due_datetime",
            "is_recurring",
            "is_completed",
            "recurrence_pattern",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "output_text",
            "error_message",
            "processing_time",
            "created_at",
            "updated_at",
            "completed_at",
            "user",
        ]

    def create(self, validated_data):
        """
        Automatically assign current user to the task.
        """
        user = self.context["request"].user
        validated_data["user"] = user
        return super().create(validated_data)