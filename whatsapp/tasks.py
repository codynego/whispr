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


from whisprai.ai.gemini_client import get_ai_response
from .models import WhatsAppMessage
from assistant.ai_core.message_handler import MessageHandler
from assistant.models import AssistantMessage
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
        print("User query:", user_query)
        user = User.objects.get(whatsapp=sender_number)
        handler = MessageHandler(user=user)
        print("Handling message with MessageHandler for user ID:", user.id)
        ai_response = handler.handle(message=user_query)

        response_text = ai_response["reply"]
        print("Gemini response:", response_text)
        print("Received Gemini response:", ai_response)


        # Save AI response as a new WhatsAppMessage (optional)
        try:
            response_message = WhatsAppMessage.objects.create(
                user=user,
                to_number=sender_number,
                message=response_text,
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
def send_whatsapp_message_task(self, task_id = None, message_id=None, message=None):
    """
    Send WhatsApp message via Cloud API
    """
    try:
        print("Sending WhatsApp message ID:", message_id, "Message:", message)
        # message = WhatsAppMessage.objects.get(id=message_id)

        if message:
            message = message

        elif message_id is None and message is None:
            print("No message_id or message provided, fetching latest message")
            try:
                # Fetch the last message based on creation time (or ID if incrementing)
                message = AssistantMessage.objects.latest('created_at')  # Make sure you have a 'created_at' field
            except AssistantMessage.DoesNotExist:
                message = None  # No messages exist yet
        
        elif message_id and message is None:
            message = AssistantMessage.objects.get(id=message_id)
        

        
        if not all([
            settings.WHATSAPP_ACCESS_TOKEN,
            settings.WHATSAPP_PHONE_NUMBER_ID,
            settings.WHATSAPP_API_URL
        ]):
            msg = 'WhatsApp API credentials not configured'
            logger.error(msg)
            # message.status = 'failed'
            # message.error_message = msg
            # message.save()
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
            
            # message.status = 'sent'
            # message.sent_at = timezone.now()
            # message.message_id = wa_msg_id
            # message.save()
            
            logger.info(f"✅ WhatsApp message sent successfully")
            return {'status': 'success', 'message_id': wa_msg_id}
        else:
            error_msg = response.text
            logger.error(f"❌ Failed to send WhatsApp message : {error_msg}")
            
            # message.status = 'failed'
            # message.error_message = error_msg
            # message.save()
            
            # Retry if it's a temporary network issue
            if response.status_code >= 500:
                raise self.retry(exc=Exception(error_msg))
            
            return {'status': 'error', 'message': error_msg}
    
    except AssistantMessage.DoesNotExist:
        logger.error(f"Message  not found in DB")
        return {'status': 'error', 'message': 'Message not found'}
    
    except Exception as e:
        logger.exception(f"Error sending WhatsApp message : {str(e)}")
        # if 'message' in locals():
        #     message.status = 'failed'
        #     message.error_message = str(e)
        #     message.save()
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



def send_whatsapp_text(user_id: int, text: str, alert_type: str = 'generic') -> dict:
    """
    Sends a WhatsApp message to a user given their ID and text.
    """
    try:
        User = get_user_model()
        user = User.objects.get(id=user_id)

        if not user.whatsapp:
            logger.warning(f"User {user_id} has no WhatsApp number configured")
            return {'status': 'error', 'message': 'User has no WhatsApp number configured'}



        # Send asynchronously
        send_whatsapp_message_task.delay(message=text)

        logger.info(f"Queued WhatsApp message for user {user_id} → {user.whatsapp}")
        return {'status': 'success', 'queued': True}

    except User.DoesNotExist:
        logger.warning(f"User {user_id} does not exist")
        return {'status': 'error', 'message': 'User not found'}
    except Exception as e:
        logger.exception(f"Error sending WhatsApp message: {str(e)}")
        return {'status': 'error', 'message': str(e)}
