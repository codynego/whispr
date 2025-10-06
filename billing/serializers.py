from rest_framework import serializers
from .models import Subscription, Payment


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model"""
    
    class Meta:
        model = Subscription
        fields = ('id', 'plan', 'status', 'start_date', 'end_date', 
                  'next_payment_date', 'amount', 'currency', 'created_at')
        read_only_fields = ('id', 'start_date', 'created_at')


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    
    class Meta:
        model = Payment
        fields = ('id', 'reference', 'amount', 'currency', 'status', 
                  'plan', 'description', 'created_at', 'paid_at')
        read_only_fields = ('id', 'reference', 'created_at', 'paid_at')


class InitializePaymentSerializer(serializers.Serializer):
    """Serializer for payment initialization"""
    plan = serializers.ChoiceField(choices=['basic', 'premium', 'enterprise'])
    email = serializers.EmailField(required=False)
