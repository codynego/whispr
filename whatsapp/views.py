from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings
from .models import WhatsAppMessage, WhatsAppWebhook
from .serializers import WhatsAppMessageSerializer, SendWhatsAppMessageSerializer
import json
from .tasks import process_whatsapp_message, send_whatsapp_message_task
from django.contrib.auth import get_user_model
from whisone.message_handler import process_user_message
from assistant.models import AssistantMessage

User = get_user_model()



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


import json
import hmac
import hashlib
from celery import chain


@csrf_exempt
def webhook(request):
    """
    WhatsApp webhook endpoint for receiving messages and status updates.
    Returns 200 for all valid events to acknowledge and stop retries.
    """
    if request.method == 'GET':
        # Webhook verification (unchanged)
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('Forbidden', status=403)
    
    elif request.method == 'POST':
        try:
            # Optional: Verify signature (add settings.WHATSAPP_APP_SECRET)
            # if not verify_signature(request.body, request.META.get('HTTP_X_HUB_SIGNATURE_256'), settings.WHATSAPP_APP_SECRET):
            #     return HttpResponse('Invalid signature', status=403)
            
            data = json.loads(request.body)
 
            # Extract common fields safely
            entry = data.get('entry', [{}])[0]
            change = entry.get('changes', [{}])[0]
            value = change.get('value', {})
            field = change.get('field')  # Should be 'messages' for WhatsApp
            
            if field != 'messages':
                return HttpResponse('OK', status=200)  # ACK unknown events
            
            # Determine event type: messages or statuses
            messages = value.get('messages')
            statuses = value.get('statuses')
            
            if messages:
                # Incoming message: Process and reply
                msg = messages[0]  # Assume single message
                sender_number = msg.get('from')
                
                # Safely get user (use filter to avoid DoesNotExist exception)
                welcome_msg = """Hello! 👋 I’m Whisone — your intelligent second brain, built to ensure you never forget anything important again.\n\nSign up in just 8 seconds to activate your unlimited memory:\nhttps://whisone.com/signup\n\nFrom now on, I’ll help you stay organized and remember everything you share with me. 🤖🧠"""
                users = User.objects.filter(whatsapp=sender_number)

                print("Fetched users for number:", sender_number, "Count:", users.count())
                if not users.exists():
                    print("Unknown user number:", sender_number)
                    send_whatsapp_message_task.delay(to_number=sender_number, message=welcome_msg)
                    return HttpResponse('OK', status=200)  # Still ACK to stop retries; handle offline later
                
                user = users.first()
                print("Known user number:", sender_number)
                
                # Log event (now works for messages too)
                event_type = 'message_received'  # Or derive from msg type
                WhatsAppWebhook.objects.create(event_type=event_type, payload=data)

                msg_text = msg.get('text', {}).get('body', '')
                if not msg_text:
                    return HttpResponse('OK', status=200)  # ACK non-text messages for now

                try:
                    AssistantMessage.objects.create(
                        user=user,
                        role='user',
                        content=msg_text
                    )
                except Exception as e:
                    print(f"Error saving user message: {e}")

                chain(
                    process_user_message.s(user.id, msg_text),
                    send_whatsapp_message_task.s(user_id=user.id, message_id=None, message=None, to_number=sender_number)
                ).apply_async()
                
            elif statuses:
                # Status update: Just log and ACK (no reply)
                status = statuses[0]  # Assume single status
                status_id = status.get('id')
                status_value = status.get('status')  # e.g., 'sent', 'delivered'
                recipient = status.get('recipient_id')  # Or 'id' for outbound
                
                # Log event
                event_type = status_value or 'unknown_status'
                WhatsAppWebhook.objects.create(event_type=event_type, payload=data)
                
            else:
                print("No messages or statuses in payload")
                # Still ACK unknown sub-events
            
            return HttpResponse('OK', status=200)  # Always ACK successes
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return HttpResponse('Invalid JSON', status=400)
        except KeyError as e:
            print(f"Missing key in payload: {e}")
            return HttpResponse('OK', status=200)  # ACK malformed but don't retry forever
        except Exception as e:
            print(f"Unexpected error: {e}")  # Use logger.error(traceback.format_exc()) in prod
            return HttpResponse('OK', status=200)  # ACK to stop retries; investigate logs
            
    return HttpResponse('Method not allowed', status=405)

# Helper function for signature verification (uncomment and add to views.py or utils)
def verify_signature(payload, signature, app_secret):
    if not signature:
        return False
    expected_sig = 'sha256=' + hmac.new(
        app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_sig)