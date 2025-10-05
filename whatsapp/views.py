from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings
from .models import WhatsAppMessage, WhatsAppWebhook
from .serializers import WhatsAppMessageSerializer, SendWhatsAppMessageSerializer
from .tasks import send_whatsapp_message_task
import json


class WhatsAppMessageListView(generics.ListAPIView):
    """List all WhatsApp messages for the authenticated user"""
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return WhatsAppMessage.objects.filter(user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_message(request):
    """Send a WhatsApp message"""
    serializer = SendWhatsAppMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    to_number = serializer.validated_data['to_number']
    message = serializer.validated_data['message']
    alert_type = serializer.validated_data.get('alert_type', '')
    
    # Create message record
    whatsapp_message = WhatsAppMessage.objects.create(
        user=request.user,
        to_number=to_number,
        message=message,
        alert_type=alert_type
    )
    
    # Trigger async task to send message
    task = send_whatsapp_message_task.delay(whatsapp_message.id)
    
    return Response({
        'message': 'WhatsApp message queued for sending',
        'message_id': whatsapp_message.id,
        'task_id': task.id
    }, status=status.HTTP_202_ACCEPTED)


@csrf_exempt
def webhook(request):
    """
    WhatsApp webhook endpoint for receiving status updates
    """
    if request.method == 'GET':
        # Webhook verification
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('Forbidden', status=403)
    
    elif request.method == 'POST':
        # Handle webhook events
        try:
            data = json.loads(request.body)
            
            # Log webhook event
            WhatsAppWebhook.objects.create(
                event_type=data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('statuses', [{}])[0].get('status', 'unknown'),
                payload=data
            )
            
            # TODO: Process webhook events (status updates, etc.)
            
            return HttpResponse('OK', status=200)
        except Exception as e:
            return HttpResponse(f'Error: {str(e)}', status=400)
    
    return HttpResponse('Method not allowed', status=405)
