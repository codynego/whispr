from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings
from .models import WhatsAppMessage, WhatsAppWebhook
from .serializers import WhatsAppMessageSerializer, SendWhatsAppMessageSerializer
import json
from .tasks import send_whatsapp_message_task
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




import json
import hmac
import hashlib
from celery import chain


import json
import hmac
import hashlib
from celery import chain

import json
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from whisone.models import UploadedFile
import requests

User = get_user_model()

@csrf_exempt
def webhook(request):
    """
    WhatsApp webhook for messages, status updates, and file uploads.
    """
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('Forbidden', status=403)


    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            entry = data.get('entry', [{}])[0]
            change = entry.get('changes', [{}])[0]
            value = change.get('value', {})
            field = change.get('field')

            if field != 'messages':
                return HttpResponse('OK', status=200)

            messages = value.get('messages')
            statuses = value.get('statuses')

            if messages:
                msg = messages[0]
                sender_number = msg.get('from')
                normalized_number = sender_number.replace("+", "").lstrip("0")
                users = User.objects.filter(whatsapp__icontains=normalized_number)

                if not users.exists():
                    welcome_msg = (
                        "Hello! 👋 I’m Whisone — your intelligent second brain..."
                    )
                    send_whatsapp_message_task.delay(to_number=sender_number, message=welcome_msg)
                    return HttpResponse('OK', status=200)

                user = users.first()
                WhatsAppWebhook.objects.create(event_type='message_received', payload=data)

                # Handle text messages
                msg_text = msg.get('text', {}).get('body')
                if msg_text:
                    try:
                        from assistant.models import AssistantMessage
                        AssistantMessage.objects.create(user=user, role='user', content=msg_text)
                    except Exception as e:
                        print(f"Error saving user message: {e}")

                    chain(
                        process_user_message.s(user.id, msg_text),
                        send_whatsapp_message_task.s(user_id=user.id, message_id=None, message=None, to_number=sender_number)
                    ).apply_async()

                # Handle file attachments
                if 'document' in msg:
                    doc = msg['document']
                    file_id = doc.get('id')
                    filename = doc.get('filename', 'uploaded_file')
                    mime_type = doc.get('mime_type', '')

                    # Download the file from WhatsApp server
                    media_url = f"https://graph.facebook.com/v17.0/{file_id}"
                    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
                    response = requests.get(media_url, headers=headers)
                    if response.status_code == 200:
                        uploaded_file = UploadedFile.objects.create(
                            user=user,
                            original_filename=filename,
                            content=response.content
                        )
                        send_whatsapp_message_task.delay(
                            to_number=sender_number,
                            message=f"File '{filename}' uploaded successfully."
                        )
                    else:
                        send_whatsapp_message_task.delay(
                            to_number=sender_number,
                            message=f"Failed to download file '{filename}'."
                        )

            elif statuses:
                status = statuses[0]
                WhatsAppWebhook.objects.create(event_type=status.get('status', 'unknown_status'), payload=data)

            return HttpResponse('OK', status=200)

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            print(f"Unexpected error: {e}")
            return HttpResponse('OK', status=200)

    return HttpResponse('Method not allowed', status=405)



# Helper function for signature verification (uncomment and add to views.py or utils)
def verify_signature(payload, signature, app_secret):
    if not signature:
        return False
    expected_sig = 'sha256=' + hmac.new(
        app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_sig)

