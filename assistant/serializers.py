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
    """Serializer for AssistantTask model"""
    
    class Meta:
        model = AssistantTask
        fields = ('id', 'task_type', 'status', 'input_text', 'context', 
                  'output_text', 'related_email_id', 'processing_time',
                  'created_at', 'completed_at')
        read_only_fields = ('id', 'status', 'output_text', 'processing_time', 
                           'created_at', 'completed_at')


class CreateAssistantTaskSerializer(serializers.Serializer):
    """Serializer for creating assistant tasks"""
    task_type = serializers.ChoiceField(choices=['reply', 'summarize', 'translate', 'analyze'])
    input_text = serializers.CharField()
    context = serializers.JSONField(required=False, allow_null=True)
    related_email_id = serializers.IntegerField(required=False, allow_null=True)
