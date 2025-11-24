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
from django.core.files.base import ContentFile
import requests



User = get_user_model()
@csrf_exempt
def webhook(request):
    """
    WhatsApp webhook — handles verification, messages, and file uploads reliably.
    """
    if request.method == 'GET':
        # Verification challenge
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
            changes = entry.get('changes', [{}])
            
            if not changes:
                return HttpResponse('OK', status=200)
                
            change = changes[0]
            value = change.get('value', {})
            field = change.get('field')

            # We only care about message events
            if field != 'messages':
                return HttpResponse('OK', status=200)

            messages = value.get('messages')
            statuses = value.get('statuses')

            if not messages:
                if statuses:
                    WhatsAppWebhook.objects.create(event_type='status_update', payload=data)
                return HttpResponse('OK', status=200)

            msg = messages[0]
            sender_number = msg.get('from')
            msg_type = msg.get('type')

            # Normalize phone number (remove + and leading zeros)
            normalized_number = sender_number.lstrip('+').lstrip('0')
            users = User.objects.filter(whatsapp__icontains=normalized_number)

            if not users.exists():
                welcome_msg = (
                    "Hello! I’m Whisone — your intelligent second brain...\n\n"
                    "Send me anything: notes, PDFs, images, voice messages — I remember everything for you."
                )
                send_whatsapp_message_task.delay(to_number=sender_number, message=welcome_msg)
                return HttpResponse('OK', status=200)

            user = users.first()
            WhatsAppWebhook.objects.create(event_type='message_received', payload=data)

            # ————— Handle Text Messages —————
            if msg_type == 'text':
                msg_text = msg['text']['body']
                try:
                    AssistantMessage.objects.create(user=user, role='user', content=msg_text)
                except Exception as e:
                    print(f"[Webhook] Failed to save AssistantMessage: {e}")

                chain(
                    process_user_message.s(user.id, msg_text),
                    send_whatsapp_message_task.s(user_id=user.id, to_number=sender_number)
                ).apply_async()

            # ————— Handle Document / File Attachments —————
            elif msg_type == 'document':
                doc = msg['document']
                file_id = doc['id']
                filename = doc.get('filename', 'document')
                mime_type = doc.get('mime_type', 'application/octet-stream')

                # Download file from WhatsApp
                media_url = f"https://graph.facebook.com/v20.0/{file_id}"
                headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

                try:
                    response = requests.get(media_url, headers=headers, timeout=60)
                    response.raise_for_status()
                except Exception as e:
                    print(f"[Webhook] Failed to download media {file_id}: {e}")
                    send_whatsapp_message_task.delay(
                        to_number=sender_number,
                        message="Sorry, I couldn't download your file. Please try sending it again."
                    )
                    return HttpResponse('OK', status=200)

                file_content = response.content
                file_size = len(file_content)

                # Create UploadedFile — let your existing save() override do its job
                uploaded_file = UploadedFile(user=user)
                
                # This triggers your model.save() → sets original_filename, size, file_type
                uploaded_file.file.save(filename, ContentFile(file_content), save=True)

                # Success message with nice formatting
                # size_str = humanize.naturalsize(file_size) if file_size > 0 else "unknown size"
                success_msg = f"Received your file:\n• {filename}\n• \n\nI’ll process it shortly!"

                send_whatsapp_message_task.delay(
                    to_number=sender_number,
                    message=success_msg
                )

            # ————— Handle Images, Audio, Video, etc. (optional future) —————
            # elif msg_type in ['image', 'audio', 'video']:
            #     ... similar logic ...

            return HttpResponse('OK', status=200)

        except json.JSONDecodeError as e:
            print(f"[Webhook] JSON decode error: {e}")
            return HttpResponse('Invalid JSON', status=400)
        except Exception as e:
            print(f"[Webhook] Unexpected error: {e}")
            return HttpResponse('OK', status=200)

    return HttpResponse('Method Not Allowed', status=405)


# Helper function for signature verification (uncomment and add to views.py or utils)
def verify_signature(payload, signature, app_secret):
    if not signature:
        return False
    expected_sig = 'sha256=' + hmac.new(
        app_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_sig)

