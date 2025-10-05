from rest_framework import serializers
from .models import EmailAccount, Email


class EmailAccountSerializer(serializers.ModelSerializer):
    """Serializer for EmailAccount model"""
    
    class Meta:
        model = EmailAccount
        fields = ('id', 'provider', 'email_address', 'is_active', 
                  'last_synced', 'created_at', 'updated_at')
        read_only_fields = ('id', 'last_synced', 'created_at', 'updated_at')


class EmailSerializer(serializers.ModelSerializer):
    """Serializer for Email model"""
    
    class Meta:
        model = Email
        fields = ('id', 'message_id', 'sender', 'recipient', 'subject', 
                  'body', 'snippet', 'importance', 'importance_score', 
                  'importance_analysis', 'is_read', 'is_starred', 
                  'received_at', 'analyzed_at', 'created_at')
        read_only_fields = ('id', 'message_id', 'created_at')


class EmailSyncSerializer(serializers.Serializer):
    """Serializer for email sync request"""
    provider = serializers.ChoiceField(choices=['gmail', 'outlook'])
    authorization_code = serializers.CharField()
