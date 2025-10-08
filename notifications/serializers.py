from rest_framework import serializers
from .models import Notification, NotificationPreference



class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'id',
            'email_notifications',
            'push_notifications',
            'sms_notifications',
            'whatsapp_notifications',
            'daily_summary',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    
    class Meta:
        model = Notification
        fields = ('id', 'type', 'title', 'message', 'related_object_id', 
                  'data', 'is_read', 'read_at', 'created_at')
        read_only_fields = ('id', 'created_at', 'read_at')
