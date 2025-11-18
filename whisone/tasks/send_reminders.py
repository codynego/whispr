# tasks.py
from celery import shared_task
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from whisone.models import Reminder
from whatsapp.tasks import send_whatsapp_text
import openai
import logging
from django.conf import settings


logger = logging.getLogger(__name__)

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_friendly_text(reminder_text: str) -> str:
    """
    Use OpenAI to rewrite reminder text in a friendly, human-like style.
    """
    try:
        prompt = f"Rewrite the following reminder in a friendly, concise, human tone:\n\n{reminder_text}"
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=60
        )
        friendly_text = response.choices[0].message.content.strip()
        return friendly_text
    except Exception as e:
        logger.warning(f"OpenAI error: {str(e)}. Using original reminder text.")
        return reminder_text



@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_and_send_reminders(self):
    """
    Check due reminders and fire off WhatsApp messages asynchronously.
    We DO NOT wait for the result → avoids blocking!
    """
    now_aware = timezone.now()
    today_start = timezone.make_aware(datetime.combine(now_aware.date(), datetime.min.time()))
    today_end = timezone.make_aware(datetime.combine(now_aware.date(), datetime.max.time()))

    due_reminders = Reminder.objects.filter(
        completed=False,
        remind_at__lte=now_aware   # Only reminders that are due now or earlier
    ).select_related('user')

    for reminder in due_reminders:
        try:
            friendly_text = generate_friendly_text(reminder.text)
            message = f"*QUICK REMINDER*\n{friendly_text}"

            # Fire and forget — this is correct!
            send_whatsapp_text.delay(reminder.user.id, message)

            # Optimistically mark as completed
            # (If WhatsApp fails, user still gets reminded next run)
            reminder.completed = True
            reminder.save(update_fields=['completed'])

            logger.info(f"Reminder {reminder.id} queued for user {reminder.user.id}")

        except Exception as exc:
            logger.error(f"Failed to process reminder {reminder.id}: {str(exc)}")
            # Optional: retry the whole task
            raise self.retry(exc=exc)