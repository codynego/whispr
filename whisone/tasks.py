# tasks.py
from celery import shared_task
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Reminder
from whatsapp.tasks import send_whatsapp_text
import openai
import logging
from django.conf import settings
# from whisone.services.gmail_service import GmailService
# from whisone.models import ImportantEmailRule
# from whatsapp.tasks import send_whatsapp_message_task



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

@shared_task
def check_and_send_reminders():
    """
    Periodic Celery task to check today's reminders and send WhatsApp messages.
    """
    now_aware = timezone.now()
    today_start = timezone.make_aware(
        datetime.combine(now_aware.date(), datetime.min.time())
    )
    today_end = timezone.make_aware(
        datetime.combine(now_aware.date(), datetime.max.time())
    )
    
    reminders = Reminder.objects.filter(
        completed=False,
        remind_at__gte=today_start,
        remind_at__lte=today_end
    )

    for r in reminders:
        if r.remind_at <= now_aware:
            # Generate friendly message via OpenAI
            message_text = generate_friendly_text(r.text)
            message_text = "**QUICK REMINDER**\n" + message_text

            # Send via WhatsApp (pass user ID for phone lookup)
            result = send_whatsapp_text(r.user.id, message_text)
            if result.get("status") == "success":
                # Mark as completed
                r.completed = True
                r.save()
                logger.info(f"Sent reminder {r.id} to user {r.user.id}")
            else:
                logger.warning(f"Failed to send reminder {r.id}: {result.get('message')}")




# @shared_task
# def watch_important_emails(user_id):
#     """
#     Periodically checks for new important emails and notifies the user.
#     """

#     from django.contrib.auth import get_user_model
#     User = get_user_model()

#     try:
#         user = User.objects.get(id=user_id)
#     except User.DoesNotExist:
#         return f"User {user_id} not found"

#     gmail = GmailService(user=user)
#     rules = ImportantEmailRule.objects.filter(user=user)

#     # 1. Fetch unread emails
#     unread_emails = gmail.fetch_unread_emails()

#     alerts = []

#     for email in unread_emails:
#         sender = email.get("sender", "")
#         subject = email.get("subject", "")

#         for rule in rules:

#             # Match sender
#             if rule.sender and rule.sender not in sender:
#                 continue

#             # Match subject keywords
#             if rule.subject_keywords:
#                 keywords = [k.strip().lower() for k in rule.subject_keywords.split(",")]
#                 if not any(k in subject.lower() for k in keywords):
#                     continue

#             alerts.append(email)

#             # Send WhatsApp alert
#             if rule.notify_whatsapp:
#                 message = (
#                     f"📩 *Important Email Alert*\n\n"
#                     f"From: {sender}\n"
#                     f"Subject: {subject}\n\n"
#                     f"Open Gmail to read."
#                 )
#                 send_whatsapp_message_task.delay(user.id, message)

#             # Mark email as notified to avoid duplicate alerts
#             gmail.mark_as_notified(email["id"])

#     return f"Processed {len(unread_emails)} emails, found {len(alerts)} important ones."
