# tasks.py
from celery import shared_task
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from .models import Reminder
from whatsapp.tasks import send_whatsapp_text
import openai
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

openai.api_key = settings.OPENAI_API_KEY

def generate_friendly_text(reminder_text: str) -> str:
    """
    Use OpenAI to rewrite reminder text in a friendly, human-like style.
    """
    try:
        prompt = f"Rewrite the following reminder in a friendly, concise, human tone:\n\n{reminder_text}"
        response = openai.ChatCompletion.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=60
        )
        friendly_text = response.choices[0].message.content.strip()
        return friendly_text
    except Exception as e:
        logger.warning(f"OpenAI error: {str(e)}. Using original reminder text.")
        return reminder_text

@shared_task
def check_and_send_reminders():
    """
    Periodic Celery task to check today's reminders and send WhatsApp messages.
    """
    today_start = datetime.combine(now().date(), datetime.min.time())
    today_end = datetime.combine(now().date(), datetime.max.time())
    
    reminders = Reminder.objects.filter(
        completed=False,
        remind_at__gte=today_start,
        remind_at__lte=today_end
    )

    for r in reminders:
        if r.remind_at <= now():
            # Generate friendly message via OpenAI
            message_text = generate_friendly_text(r.text)

            # Send via WhatsApp
            result = send_whatsapp_text(r.user.id, message_text)
            if result.get("status") == "success":
                # Mark as completed
                r.completed = True
                r.save()
                logger.info(f"Sent reminder {r.id} to user {r.user.id}")
            else:
                logger.warning(f"Failed to send reminder {r.id}: {result.get('message')}")
