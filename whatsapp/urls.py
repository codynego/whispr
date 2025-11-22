from django.urls import path
from .views import WhatsAppMessageListView, webhook

urlpatterns = [
    path('messages/', WhatsAppMessageListView.as_view(), name='whatsapp-message-list'),
    path('webhook/', webhook, name='whatsapp-webhook'),
]
