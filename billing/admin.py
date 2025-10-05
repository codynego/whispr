from django.contrib import admin
from .models import Subscription, Payment


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'amount', 'start_date', 'end_date', 'next_payment_date')
    list_filter = ('plan', 'status')
    search_fields = ('user__email', 'subscription_code', 'customer_code')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'amount', 'status', 'plan', 'created_at', 'paid_at')
    list_filter = ('status', 'plan')
    search_fields = ('reference', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'paid_at')
