from celery import shared_task
from django.conf import settings
from django.utils import timezone
import openai
import logging
import time
from .models import AssistantTask

logger = logging.getLogger(__name__)


@shared_task
def check_due_tasks():
    """
    Periodic task to check all pending tasks and execute them if due.
    """
    now = timezone.now()
    due_tasks = Task.objects.filter(
        due_datetime__lte=now,
        is_completed=False
    )

    for task in due_tasks:
        try:
            print(f"⚙️ Executing Task: {task.task_type} ({task.id}) for user {task.user.username}")

            # Handle based on action type
            if task.task_type in ["reminder", "set_reminder"]:
                execute_reminder(task)
            elif task.task_type in ["email_send", "send_email"]:
                execute_email(task)
            elif task.task_type in ["reply", "reply_email"]:
                execute_reply(task)
            else:
                print(f"⚠️ Unknown action type: {task.task_type}")

            # Mark as completed
            task.is_completed = True
            task.completed_at = now
            task.save()

        except Exception as e:
            print(f"❌ Error executing task {task.id}: {e}")

def execute_reminder(task):
    """Send reminder notification."""
    print(f"🔔 Reminder: {task.task_title} - {task.context}")

def execute_email(task):
    """Simulate email sending."""
    print(f"📧 Sending scheduled email: {task.task_title}")
    # You can integrate your Email sending function here
    # e.g. EmailService.send_email(receiver, subject, body)

def execute_reply(task):
    """Simulate email reply."""
    print(f"📨 Sending scheduled reply for: {task.context}")




import logging
from datetime import datetime
from django.utils import timezone
# from emails.tasks import send_email_task
# from core.tasks import create_reminder_task
# from .whatsapp_utils import send_whatsapp_message  # a helper to reply on Wh

logger = logging.getLogger(__name__)

def execute_ai_action(user, ai_response, sender_number="2349033814065"):
    """
    Executes AI actions based on Gemini's structured response.
    Handles email sending, reminders, or default replies.
    """

    print("parsing ai_response:")
    intent = ai_response.get("intent")
    required_fields = ai_response.get("required_fields", {})
    fields = ai_response.get("fields", {})
    reply = ai_response.get("reply", "I didn’t quite get that.")

    # === Case 1: Missing required information ===
    if required_fields:
        missing_prompts = []
        for field in required_fields:
            missing_prompts.append(f"I’ll need the {field.replace('_', ' ')} to continue.")
        follow_up = " ".join(missing_prompts)
        #send_whatsapp_message(to_number=sender_number, message=f"{reply}\n{follow_up}")
        logger.info(f"Requested missing info from user {user.email}")
        return "awaiting_more_info"

    # === Case 2: Send Email Intent ===
    elif intent == "send_email":
        recipient = fields.get("to")
        subject = fields.get("subject", "")
        body = fields.get("body", "")

        if not recipient or not body:
            pass
            # send_whatsapp_message(
            #     to_number=sender_number,
            #     message="I need the recipient and body to send the email."
            # )
            return "incomplete_data"

        # Trigger async email sending
        # send_email_task.delay(user.id, recipient, subject, body)
        # send_whatsapp_message(
        #     to_number=sender_number,
        #     message=f"📧 Sending email to {recipient}...\nSubject: {subject}\n\n{body}"
        # )
        print("sending email to", recipient)
        logger.info(f"Email task created for {user.email} to {recipient}")
        return "email_sent"

    # === Case 3: Set Reminder Intent ===
    elif intent == "set_reminder":
        reminder_time = fields.get("time")
        reminder_msg = fields.get("message", "You have a reminder.")

        if not reminder_time:
            pass
            # send_whatsapp_message(
            #     to_number=sender_number,
            #     message=f"{reply}\nWhen should I remind you?"
            # )
            # return "awaiting_time"

        # Example: parse the time string into a datetime
        try:
            reminder_dt = datetime.fromisoformat(reminder_time)
        except Exception:
            reminder_dt = timezone.now()  # fallback

        # create_reminder_task.delay(user.id, reminder_dt.isoformat(), reminder_msg)
        # send_whatsapp_message(
        #     to_number=sender_number,
        #     message=f"⏰ Reminder set for {reminder_dt.strftime('%I:%M %p')} - {reminder_msg}"
        # )
        print("setting reminder for", reminder_dt)
        logger.info(f"Reminder created for {user.email}")
        return "reminder_set"

    # # === Case 4: Reply / General Intent ===
    # elif intent in ["reply", "none"] or not intent:
    #     send_whatsapp_message(to_number=sender_number, message=reply)
    #     return "replied"

    # === Fallback ===
    else:
        send_whatsapp_message(
            to_number=sender_number,
            message=f"I’m not sure how to handle that yet.\n{reply}"
        )
        logger.warning(f"Unknown intent from {user.email}: {intent}")
        return "unknown_intent"

