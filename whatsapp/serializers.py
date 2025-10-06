from rest_framework import serializers
from .models import WhatsAppMessage, WhatsAppWebhook


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    """Serializer for WhatsAppMessage model"""
    
    class Meta:
        model = WhatsAppMessage
        fields = ('id', 'to_number', 'message', 'message_id', 'status', 
                  'alert_type', 'created_at', 'sent_at')
        read_only_fields = ('id', 'message_id', 'status', 'created_at', 'sent_at')


class SendWhatsAppMessageSerializer(serializers.Serializer):
    """Serializer for sending WhatsApp messages"""
    to_number = serializers.CharField(max_length=20)
    message = serializers.CharField()
    alert_type = serializers.CharField(required=False, allow_blank=True)
