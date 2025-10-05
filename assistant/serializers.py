from rest_framework import serializers
from .models import AssistantTask


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
