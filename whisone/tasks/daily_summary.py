# whisone/tasks/daily_summary.py

from celery import chain, shared_task, group
from django.contrib.auth import get_user_model
from django.utils import timezone
import json
import logging

from whisone.services.gmail_service import GmailService
from whisone.services.calendar_service import GoogleCalendarService
from whisone.services.todo_service import TodoService
from whisone.services.note_service import NoteService
from whisone.services.reminder_service import ReminderService
from whatsapp.tasks import send_whatsapp_text
from .openai_client import generate_daily_summary
from whisone.models import Integration
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)
User = get_user_model()


# Add this function anywhere (e.g. in openai_client.py or a utils.py)

def clean_for_whatsapp(text: str) -> str:
    """
    Clean GPT summary for WhatsApp:
    - Remove ** (double asterisks) used for section headers
    - Keep single * for bold (WhatsApp native bold)
    - Clean up common GPT formatting issues
    - Add nice emojis for sections
    """
    lines = text.split("\n")
    result = []

    # Section header mapping: replace **Header** → 🌅 Header (with single * for bold if you want)
    header_map = {
        "Morning Briefing": "🌅 *Morning Briefing*",
        "Important Emails": "📧 *Important Emails*",
        "Today’s Schedule": "📅 *Today’s Schedule*",
        "Tasks & Todos": "✅ *Tasks & Todos*",
        "Overdue Tasks": "⚠️ Overdue Tasks",
        "Due Today": "📌 Due Today",
        "Reminders": "⏰ *Reminders*",
        "Notes": "🗒️ *Notes*",
        "Smart Suggestion": "💡 *Smart Suggestion*",
    }

    for line in lines:
        stripped = line.strip()

        # Skip empty lines with just stars
        if stripped in ["*", "**", "***", "----", "---"]:
            continue

        # Replace known section headers (with or without **)
        replaced = False
        for old, new in header_map.items():
            if old.lower() in stripped.lower():
                if stripped.startswith("**") or stripped.startswith("*"):
                    line = new
                    replaced = True
                    break
                elif stripped == old:
                    line = new
                    replaced = True
                    break

        # Remove ** but keep single * (this is the key part)
        line = line.replace("**", "")  # Removes all double asterisks

        # Clean bullet points: turn "- *text*" → "• text" or keep "*text*" as bold
        if stripped.startswith("- *") and stripped.endswith("*"):
            # Was a bold bullet → keep bold
            line = "• *" + stripped[3:-1].strip() + "*"
        elif stripped.startswith("- "):
            line = "• " + stripped[2:].strip()

        # Clean reminder times: "*1:00 PM*" → "*1:00 PM*"
        if ": " in line and "*" in line:
            # Preserve time in bold if already formatted
            pass

        result.append(line.rstrip())

    # Join and clean extra blank lines
    final = "\n".join(result)
    final = "\n\n".join([part.strip() for part in final.split("\n\n") if part.strip()])
    return final.strip() + "\n"


def safe_serialize(data):
    """Convert anything (QuerySet, model instances, datetimes) → clean JSON-serializable dict/list"""
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder, default=str))


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_daily_emails(self, user_id):
    try:
        user = User.objects.get(id=user_id)
        integration = Integration.objects.filter(user=user, provider="gmail").first()

        emails = []
        if integration:
            creds = {
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "refresh_token": integration.refresh_token,
                "access_token": integration.access_token,
                "user_email": user.email,
            }
            service = GmailService(**creds)
            emails = service.get_emails_last_24h() or []
            logger.info(f"User {user_id}: Fetched {len(emails)} emails")
        else:
            logger.info(f"User {user_id}: No Gmail integration")

        return {"emails": safe_serialize(emails)}
    except Exception as exc:
        logger.error(f"fetch_daily_emails failed for user {user_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def fetch_daily_calendar(previous_result, user_id):
    try:
        user = User.objects.get(id=user_id)
        integration = Integration.objects.filter(user=user, provider="google_calendar").first()

        events = []
        if integration:
            creds = {
                "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
                "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
                "refresh_token": integration.refresh_token,
                "access_token": integration.access_token,
                "user_email": user.email,
            }
            service = GoogleCalendarService(**creds)
            raw_events = service.get_events_for_today()
            events = safe_serialize(raw_events) if raw_events else []
            logger.info(f"User {user_id}: Fetched {len(events)} calendar events")

        previous_result["calendar"] = events
        return previous_result
    except Exception as exc:
        logger.error(f"fetch_daily_calendar failed: {exc}")
        return previous_result  # Continue chain even if calendar fails


@shared_task
def fetch_daily_todos(previous_result, user_id):
    try:
        user = User.objects.get(id=user_id)
        service = TodoService(user=user)

        overdue_qs = service.get_overdue_todos().values('id', 'task', 'done', 'created_at')
        today_qs = service.get_todos_for_today().values('id', 'task', 'done', 'created_at')

        todos = {
            "overdue": safe_serialize(overdue_qs),
            "today": safe_serialize(today_qs),
        }

        previous_result["todos"] = todos
        total = len(todos["overdue"]) + len(todos["today"])
        logger.info(f"User {user_id}: Fetched {total} todos ({len(todos['overdue'])} overdue)")
        return previous_result
    except Exception as exc:
        logger.error(f"fetch_daily_todos failed: {exc}")
        previous_result["todos"] = {"overdue": [], "today": []}
        return previous_result


@shared_task
def fetch_daily_reminders(previous_result, user_id):
    try:
        user = User.objects.get(id=user_id)
        service = ReminderService(user=user)
        reminders_qs = service.get_upcoming_reminders().values('id', 'text', 'remind_at', 'completed')

        reminders = safe_serialize(reminders_qs)
        previous_result["reminders"] = reminders
        logger.info(f"User {user_id}: Fetched {len(reminders)} reminders")
        return previous_result
    except Exception as exc:
        logger.error(f"fetch_daily_reminders failed: {exc}")
        previous_result["reminders"] = []
        return previous_result


@shared_task
def fetch_daily_notes(previous_result, user_id):
    try:
        user = User.objects.get(id=user_id)
        service = NoteService(user=user)
        notes_qs = service.get_recent_notes(limit=10).values('id', 'content', 'updated_at')

        notes = safe_serialize(notes_qs)
        previous_result["notes"] = notes
        logger.info(f"User {user_id}: Fetched {len(notes)} notes")
        return previous_result
    except Exception as exc:
        logger.error(f"fetch_daily_notes failed: {exc}")
        previous_result["notes"] = []
        return previous_result


@shared_task
def generate_summary_and_send(previous_result, user_id):
    try:
        # Ensure all keys exist (defensive)
        data = {
            "emails": previous_result.get("emails", []),
            "calendar": previous_result.get("calendar", []),
            "todos": previous_result.get("todos", {"overdue": [], "today": []}),
            "reminders": previous_result.get("reminders", []),
            "notes": previous_result.get("notes", []),
        }

        logger.info(f"User {user_id}: Generating summary with data keys: {list(data.keys())}")
        summary = generate_daily_summary(data)
        summary = clean_for_whatsapp(summary)

        send_whatsapp_text.delay(user_id=user_id, text=summary)
        logger.info(f"User {user_id}: Summary sent via WhatsApp")
        return {"status": "success", "summary_length": len(summary)}
    except Exception as exc:
        logger.error(f"generate_summary_and_send failed for {user_id}: {exc}")
        return {"status": "failed", "error": str(exc)}


@shared_task
def run_daily_summary():
    users = User.objects.filter(is_active=True)
    if not users.exists():
        return "No active users"

    jobs = []
    for user in users:
        workflow = chain(
            fetch_daily_emails.s(user.id),
            fetch_daily_calendar.s(user.id),
            fetch_daily_todos.s(user.id),
            fetch_daily_reminders.s(user.id),
            fetch_daily_notes.s(user.id),
            generate_summary_and_send.s(user.id),
        )
        jobs.append(workflow)

    group(jobs).apply_async()
    logger.info(f"Started daily summary for {users.count()} users")
    return f"Started daily summary for {users.count()} users"