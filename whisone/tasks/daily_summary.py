# whisone/tasks/daily_summary.py

from celery import chain, shared_task, group
from django.contrib.auth import get_user_model
from django.utils import timezone
import json
import logging
from whisone.models import DailySummary
from datetime import date
from whisone.services.todo_service import TodoService
from whisone.services.note_service import NoteService
from whisone.services.reminder_service import ReminderService
from whatsapp.tasks import send_whatsapp_text
from .openai_client import generate_overall_daily_summary  # new function for overall summary
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)
User = get_user_model()


def clean_for_whatsapp(text: str) -> str:
    """
    Clean GPT summary for WhatsApp:
    - Preserve the full natural, beautiful narrative from GPT
    - Remove any unnecessary markdown artifacts (** → *, etc.)
    - Keep it as pure, flowing text
    - Add a simple, friendly header only
    - Add a gentle positive note on quiet days
    - No section headers, no forced structure
    """
    if not text or not text.strip():
        return "Morning Briefing\n\nIt's a calm start to the day with no pending updates. Enjoy the peace and take it easy — you're doing great!"

    # Clean markdown bold/italic artifacts
    cleaned = text.replace("**", "").replace("__", "").replace("***", "").strip()

    # Split into lines, remove empty ones, rejoin into natural paragraphs
    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    body = "\n\n".join(lines)

    # Detect if it's a quiet/empty day to add a warm closing note
    lower_body = body.lower()
    is_quiet = (
        "no overdue" in lower_body or
        "no tasks" in lower_body or
        "no reminders" in lower_body or
        "clear" in lower_body or
        "breather" in lower_body or
        "quiet" in lower_body
    )

    result = ["Morning Briefing\n", body]

    if is_quiet:
        result.append("\nA peaceful day ahead — perfect for rest, reflection, or whatever inspires you today.")

    return "\n".join(result).strip() + "\n"


def safe_serialize(data):
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder, default=str))


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
        previous_result["reminders"] = safe_serialize(reminders_qs)
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
        notes_qs = service.get_recent_notes().values('id', 'content', 'updated_at')
        previous_result["notes"] = safe_serialize(notes_qs)
        return previous_result
    except Exception as exc:
        logger.error(f"fetch_daily_notes failed: {exc}")
        previous_result["notes"] = []
        return previous_result


@shared_task
def generate_summary_and_send(previous_result, user_id):
    try:
        user = User.objects.get(id=user_id)

        # Prepare the data for summary
        data = {
            "todos": previous_result.get("todos", {"overdue": [], "today": []}),
            "reminders": previous_result.get("reminders", []),
            "notes": previous_result.get("notes", []),
        }

        # Generate a human-readable overall summary
        summary_text = generate_overall_daily_summary(user=user, data=data)
        print("Generated summary text:", summary_text)
        # clean_text = generate_overall_daily_summary(user=user, data=data)
        clean_text = clean_for_whatsapp(summary_text)
        print("Cleaned summary text for WhatsApp:", clean_text)


        # Save to database
        today = date.today()
        summary_obj, created = DailySummary.objects.update_or_create(
            user=user,
            summary_date=today,
            defaults={"summary_text": clean_text, "raw_data": data}
        )

        # Send to WhatsApp
        send_whatsapp_text.delay(user_id=user_id, text=clean_text)

        return {
            "status": "success",
            "summary_length": len(clean_text),
            "summary_id": summary_obj.id
        }

    except Exception as exc:
        logger.error(f"generate_summary_and_send failed for {user_id}: {exc}")
        return {"status": "failed", "error": str(exc)}


@shared_task
def run_daily_summary():
    initial_result = {}
    users = User.objects.filter(is_active=True)
    if not users.exists():
        return "No active users"

    jobs = []
    for user in users:
        workflow = chain(
            fetch_daily_todos.s(previous_result=initial_result, user_id=user.id),
            fetch_daily_reminders.s(user_id=user.id),
            fetch_daily_notes.s(user_id=user.id),
            generate_summary_and_send.s(user_id=user.id),
        )
        jobs.append(workflow)

    group(jobs).apply_async()
    logger.info(f"Started daily summary for {users.count()} users")
    return f"Started daily summary for {users.count()} users"
