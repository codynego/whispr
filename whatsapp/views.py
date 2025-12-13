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
from whisone.tasks.process_file_upload import process_uploaded_file
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
    WhatsApp webhook endpoint.
    - Verifies webhook on GET.
    - On POST, checks user existence and first interaction.
    - Sends welcome/signup messages.
    - Handles text + document uploads.
    """

    # --------------------------
    # WEBHOOK VERIFICATION (GET)
    # --------------------------
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, content_type='text/plain')

        return HttpResponse('Forbidden', status=403)

    # --------------------------
    # MAIN LOGIC (POST)
    # --------------------------
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

            # ------------------------------------------------------
            # HANDLE INCOMING MESSAGE
            # ------------------------------------------------------
            if messages:
                msg = messages[0]
                sender_number = msg.get('from')

                # Normalize phone
                normalized = sender_number.replace("+", "")
                normalized = normalized.lstrip("0")

                # Try match
                user = User.objects.filter(whatsapp__icontains=normalized).first()

                # ------------------------------------------------------
                # USER DOES NOT EXIST → SEND SIGNUP MESSAGE
                # ------------------------------------------------------
                if not user:
                    signup_msg = (
                        "Hey! 👋 I’m Whisone — your intelligent second brain.\n\n"
                        "It looks like you aren’t registered yet.\n\n"
                        "Create your account in *8 seconds* to start saving notes, files, reminders and more:\n"
                        "https://whisone.com/auth/register"
                    )
                    send_whatsapp_message_task.delay(
                        to_number=sender_number,
                        message=signup_msg
                    )
                    return HttpResponse('OK', status=200)

                # ------------------------------------------------------
                # USER EXISTS → CHECK FIRST INTERACTION
                # ------------------------------------------------------
                print("user first interaction", user.first_interaction_time)
                if user.first_interaction_time is None:
                    user.first_interaction_time = timezone.now()
                    user.save(update_fields=["first_interaction_time"])

                    welcome_msg = (
                        "Welcome back! 🎉\n\n"
                        "Your second brain is now activated.\n"
                        "You can send *notes, reminders, ideas, files*, and I’ll store them automatically.\n"
                        "to access your dashboard: please login\n"
                        "https://whisone.com/auth/login"
                    )
                    send_whatsapp_message_task.delay(
                        to_number=sender_number,
                        message=welcome_msg
                    )

                # Save webhook event
                WhatsAppWebhook.objects.create(
                    event_type='message_received',
                    payload=data
                )

                # ------------------------------------------------------
                # TEXT MESSAGE HANDLING
                # ------------------------------------------------------
                msg_text = msg.get('text', {}).get('body')
                if msg_text:
                    from assistant.models import AssistantMessage
                    AssistantMessage.objects.create(
                        user=user,
                        role='user',
                        content=msg_text
                    )

                    chain(
                        process_user_message.s(user.id, msg_text),
                        send_whatsapp_message_task.s(
                            user_id=user.id,
                            message_id=None,
                            message=None,
                            to_number=sender_number
                        )
                    ).apply_async()

                # ------------------------------------------------------
                # DOCUMENT UPLOAD HANDLING
                # ------------------------------------------------------
                if 'document' in msg:
                    doc = msg['document']
                    media_id = doc.get('id')
                    filename = doc.get('filename', 'uploaded_file')

                    try:
                        # 1️⃣ Get download URL
                        info_url = f"https://graph.facebook.com/v17.0/{media_id}?fields=url"
                        headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

                        info_resp = requests.get(info_url, headers=headers)
                        info_resp.raise_for_status()
                        download_url = info_resp.json().get('url')
                        if not download_url:
                            raise ValueError("Could not retrieve media download URL.")

                        # 2️⃣ Download file
                        file_resp = requests.get(download_url, headers=headers)
                        file_resp.raise_for_status()

                        uploaded_file = UploadedFile(user=user, original_filename=filename)
                        uploaded_file.file = ContentFile(file_resp.content, name=filename)
                        uploaded_file.save()

                        process_uploaded_file.delay(uploaded_file.id)

                        send_whatsapp_message_task.delay(
                            to_number=sender_number,
                            message=f"Your file '{filename}' has been saved successfully!"
                        )

                    except Exception as e:
                        send_whatsapp_message_task.delay(
                            to_number=sender_number,
                            message=f"Sorry, I couldn't process the file '{filename}'."
                        )

            # ------------------------------------------------------
            # HANDLE STATUS UPDATES
            # ------------------------------------------------------
            elif statuses:
                status = statuses[0]
                WhatsAppWebhook.objects.create(
                    event_type=status.get('status', 'unknown_status'),
                    payload=data
                )

            return HttpResponse('OK', status=200)

        except Exception as e:
            print(f"Webhook error: {e}")
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

