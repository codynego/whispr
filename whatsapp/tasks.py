from celery import shared_task
from django.conf import settings
from django.utils import timezone
import requests
import logging
from .models import WhatsAppMessage

logger = logging.getLogger(__name__)


@shared_task
def send_whatsapp_message_task(message_id):
    """
    Send WhatsApp message via Cloud API
    """
    try:
        message = WhatsAppMessage.objects.get(id=message_id)
        
        if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
            logger.error('WhatsApp API credentials not configured')
            message.status = 'failed'
            message.error_message = 'WhatsApp API credentials not configured'
            message.save()
            return {'status': 'error', 'message': 'API credentials not configured'}
        
        # WhatsApp Cloud API endpoint
        url = f"{settings.WHATSAPP_API_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        
        headers = {
            'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': message.to_number,
            'type': 'text',
            'text': {
                'body': message.message
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            response_data = response.json()
            message.message_id = response_data.get('messages', [{}])[0].get('id')
            message.status = 'sent'
            message.sent_at = timezone.now()
            message.save()
            
            logger.info(f'WhatsApp message {message_id} sent successfully')
            return {'status': 'success', 'message_id': message.message_id}
        else:
            message.status = 'failed'
            message.error_message = response.text
            message.save()
            
            logger.error(f'Failed to send WhatsApp message {message_id}: {response.text}')
            return {'status': 'error', 'message': response.text}
            
    except WhatsAppMessage.DoesNotExist:
        logger.error(f'WhatsApp message {message_id} not found')
        return {'status': 'error', 'message': 'Message not found'}
    except Exception as e:
        logger.error(f'Error sending WhatsApp message {message_id}: {str(e)}')
        if 'message' in locals():
            message.status = 'failed'
            message.error_message = str(e)
            message.save()
        return {'status': 'error', 'message': str(e)}


@shared_task
def send_email_alert_via_whatsapp(user_id, email_id):
    """
    Send WhatsApp alert for important email
    """
    try:
        from django.contrib.auth import get_user_model
        from emails.models import Email
        
        User = get_user_model()
        user = User.objects.get(id=user_id)
        email = Email.objects.get(id=email_id)
        
        if not user.whatsapp:
            logger.warning(f'User {user_id} has no WhatsApp number configured')
            return {'status': 'error', 'message': 'No WhatsApp number configured'}
        
        alert_message = f"""
🔔 Important Email Alert

From: {email.sender}
Subject: {email.subject}

{email.snippet[:200]}...

Priority: {email.importance.upper()}
"""
        
        whatsapp_message = WhatsAppMessage.objects.create(
            user=user,
            to_number=user.whatsapp,
            message=alert_message,
            alert_type='email_importance',
            related_email_id=email_id
        )
        
        # Send the message
        return send_whatsapp_message_task.delay(whatsapp_message.id)
        
    except Exception as e:
        logger.error(f'Error sending email alert: {str(e)}')
        return {'status': 'error', 'message': str(e)}
