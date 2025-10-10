# core/tasks/whatsapp_tasks.py
from celery import shared_task
from django.conf import settings
from django.utils import timezone
import requests
import logging
from .models import WhatsAppMessage
from django.contrib.auth import get_user_model
import json

logger = logging.getLogger(__name__)


from whisprai.ai.gemini_client import get_gemini_response
from .models import WhatsAppMessage
import logging

User = get_user_model()

logger = logging.getLogger(__name__)

def process_whatsapp_message(message_instance):
    """
    Takes a WhatsAppMessage instance, sends its text to Gemini,
    and returns the AI-generated response.
    """
    try:
        payload_dict = message_instance

        text_body = payload_dict['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
        sender_number = payload_dict['entry'][0]['changes'][0]['value']['messages'][0]['from']
        # Construct prompt from incoming message

        user_query = text_body

        user = User.objects.get(whatsapp=sender_number)


        # Call Gemini AI

        ai_response = get_gemini_response(prompt=user_query, user=user)


        # Save AI response as a new WhatsAppMessage (optional)
        try:
            response_message = WhatsAppMessage.objects.create(
                user=user,
                to_number=sender_number,
                message=ai_response,
                alert_type='auto_reply'
            )

        except Exception as e:
            print("Error creating response WhatsAppMessage:", str(e))
            logger.error(f"Error creating response WhatsAppMessage: {str(e)}")
            return None
        return response_message

    except Exception as e:
        logger.error(f"Error processing WhatsApp message {message_instance.id}: {str(e)}")
        return None


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def send_whatsapp_message_task(self, message_id):
    """
    Send WhatsApp message via Cloud API
    """
    try:
        print("Sending WhatsApp message ID:", message_id)
        message = WhatsAppMessage.objects.get(id=message_id)

        
        if not all([
            settings.WHATSAPP_ACCESS_TOKEN,
            settings.WHATSAPP_PHONE_NUMBER_ID,
            settings.WHATSAPP_API_URL
        ]):
            msg = 'WhatsApp API credentials not configured'
            logger.error(msg)
            message.status = 'failed'
            message.error_message = msg
            message.save()
            return {'status': 'error', 'message': msg}
        # Construct API request
        url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json',
        }

        payload = {
            'messaging_product': 'whatsapp',
            'to': message.to_number,
            'type': 'text',
            'text': {'body': message.message}
        }
        print("WhatsApp API payload:", payload)
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            wa_msg_id = response_data.get('messages', [{}])[0].get('id', None)
            
            message.status = 'sent'
            message.sent_at = timezone.now()
            message.message_id = wa_msg_id
            message.save()
            
            logger.info(f"✅ WhatsApp message {message_id} sent successfully")
            return {'status': 'success', 'message_id': wa_msg_id}
        else:
            error_msg = response.text
            logger.error(f"❌ Failed to send WhatsApp message {message_id}: {error_msg}")
            
            message.status = 'failed'
            message.error_message = error_msg
            message.save()
            
            # Retry if it's a temporary network issue
            if response.status_code >= 500:
                raise self.retry(exc=Exception(error_msg))
            
            return {'status': 'error', 'message': error_msg}
    
    except WhatsAppMessage.DoesNotExist:
        logger.error(f"Message {message_id} not found in DB")
        return {'status': 'error', 'message': 'Message not found'}
    
    except Exception as e:
        logger.exception(f"Error sending WhatsApp message {message_id}: {str(e)}")
        if 'message' in locals():
            message.status = 'failed'
            message.error_message = str(e)
            message.save()
        return {'status': 'error', 'message': str(e)}


# @shared_task
def send_email_alert_via_whatsapp(user_id, email_id):
    """
    Send WhatsApp alert for important or priority email
    """
    try:
        from django.contrib.auth import get_user_model
        from emails.models import Email
        
        User = get_user_model()
        user = User.objects.get(id=user_id)
        email = Email.objects.get(id=email_id)
        
        if not user.whatsapp:
            logger.warning(f"User {user_id} has no WhatsApp number configured")
            return {'status': 'error', 'message': 'User has no WhatsApp number configured'}
        
        alert_message = f"""
🔔 *New Important Email Alert*

*From:* {email.sender}
*Subject:* {email.subject}

{email.snippet[:200]}...

*Priority:* {email.importance.upper()}
"""
        
        whatsapp_message = WhatsAppMessage.objects.create(
            user=user,
            to_number=user.whatsapp,
            message=alert_message.strip(),
            alert_type='email_alert',
            related_email_id=email_id
        )
        
        # Send asynchronously
        send_whatsapp_message_task.delay(whatsapp_message.id)
        logger.info(f"Queued WhatsApp alert for email {email_id} → {user.whatsapp}")
        return {'status': 'success', 'queued': True}
    
    except Exception as e:
        logger.exception(f"Error sending WhatsApp email alert: {str(e)}")
        return {'status': 'error', 'message': str(e)}
