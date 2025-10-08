from rest_framework import serializers
from .models import EmailAccount, Email
from .models import UserEmailRule




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



class UserEmailRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserEmailRule
        fields = [
            "id",
            "name",
            "rule_type",
            "value",
            "importance",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_value(self, value):
        rule_type = self.initial_data.get("rule_type")
        if rule_type in ["sender", "keyword", "subject", "body"] and not value:
            raise serializers.ValidationError("This rule type requires a value.")
        return value
