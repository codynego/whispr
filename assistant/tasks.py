from celery import shared_task
from django.conf import settings
from django.utils import timezone
import openai
import logging
import time
from .models import AssistantTask

logger = logging.getLogger(__name__)


@shared_task
def process_assistant_task(task_id):
    """
    Process assistant tasks using OpenAI
    """
    try:
        task = AssistantTask.objects.get(id=task_id)
        task.status = 'processing'
        task.save()
        
        start_time = time.time()
        
        if not settings.OPENAI_API_KEY:
            raise ValueError('OpenAI API key not configured')
        
        openai.api_key = settings.OPENAI_API_KEY
        
        # Prepare prompt based on task type
        if task.task_type == 'reply':
            system_prompt = "You are a helpful email assistant. Generate a professional reply to the following email."
            user_prompt = f"Email content:\n{task.input_text}\n\nGenerate a professional reply:"
        
        elif task.task_type == 'summarize':
            system_prompt = "You are a helpful assistant. Summarize the following content concisely."
            user_prompt = f"Content to summarize:\n{task.input_text}"
        
        elif task.task_type == 'translate':
            target_language = task.context.get('target_language', 'English') if task.context else 'English'
            system_prompt = f"You are a professional translator. Translate the following text to {target_language}."
            user_prompt = task.input_text
        
        elif task.task_type == 'analyze':
            system_prompt = "You are an analytical assistant. Analyze the following content and provide insights."
            user_prompt = f"Content to analyze:\n{task.input_text}"
        
        else:
            raise ValueError(f'Unknown task type: {task.task_type}')
        
        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        output = response.choices[0].message.content
        processing_time = time.time() - start_time
        
        # Update task
        task.output_text = output
        task.status = 'completed'
        task.processing_time = processing_time
        task.completed_at = timezone.now()
        task.save()
        
        logger.info(f'Assistant task {task_id} completed in {processing_time:.2f}s')
        return {
            'status': 'success',
            'task_id': task_id,
            'processing_time': processing_time
        }
        
    except AssistantTask.DoesNotExist:
        logger.error(f'Assistant task {task_id} not found')
        return {'status': 'error', 'message': 'Task not found'}
    
    except Exception as e:
        logger.error(f'Error processing assistant task {task_id}: {str(e)}')
        if 'task' in locals():
            task.status = 'failed'
            task.error_message = str(e)
            task.save()
        return {'status': 'error', 'message': str(e)}



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

