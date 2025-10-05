from django.urls import path
from .views import (
    SubscriptionDetailView, PaymentListView,
    initialize_payment, verify_payment, webhook
)

urlpatterns = [
    path('subscription/', SubscriptionDetailView.as_view(), name='subscription-detail'),
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('payments/initialize/', initialize_payment, name='payment-initialize'),
    path('payments/verify/<str:reference>/', verify_payment, name='payment-verify'),
    path('webhook/', webhook, name='billing-webhook'),
]
