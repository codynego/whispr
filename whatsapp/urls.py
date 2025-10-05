from django.urls import path
from .views import WhatsAppMessageListView, send_message, webhook

urlpatterns = [
    path('messages/', WhatsAppMessageListView.as_view(), name='whatsapp-message-list'),
    path('send/', send_message, name='whatsapp-send'),
    path('webhook/', webhook, name='whatsapp-webhook'),
]
