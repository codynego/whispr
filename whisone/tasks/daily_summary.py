# whisone/tasks/daily_summary.py

from celery import chain, shared_task, group
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import json

from whisone.services.gmail_service import GmailService
from whisone.services.calendar_service import GoogleCalendarService
from whisone.services.todo_service import TodoService
from whisone.services.note_service import NoteService
from whisone.services.reminder_service import ReminderService
from whatsapp.tasks import send_whatsapp_text
from .openai_client import generate_daily_summary
from whisone.models import Integration
from django.conf import settings

User = get_user_model()


def queryset_to_list(qs):
    """Safely convert any QuerySet → list of dicts (JSON-serializable)"""
    return json.loads(json.dumps(list(qs), cls=DjangoJSONEncoder))


@shared_task
def fetch_daily_emails(user_id):
    user = User.objects.get(id=user_id)
    integration = Integration.objects.filter(user=user, provider="gmail").first()

    emails = []
    if integration:
        google_creds = {
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "refresh_token": integration.refresh_token,
            "access_token": integration.access_token,
            "user_email": user.email,
        }
        service = GmailService(**google_creds)
        emails = service.get_emails_last_24h()
        print("Fetched emails:", len(emails))

    return {"emails": emails or []}


@shared_task
def fetch_daily_calendar(previous_result, user_id):
    user = User.objects.get(id=user_id)
    integration = Integration.objects.filter(user=user, provider="google_calendar").first()

    events = []
    if integration:
        google_creds = {
            "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
            "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
            "refresh_token": integration.refresh_token,
            "access_token": integration.access_token,
            "user_email": user.email,
        }
        service = GoogleCalendarService(**google_creds)
        raw_events = service.get_events_for_today()
        events = queryset_to_list(raw_events) if hasattr(raw_events, '__queryset__') else raw_events

    previous_result["calendar"] = events
    return previous_result


@shared_task
def fetch_daily_todos(previous_result, user_id):
    user = User.objects.get(id=user_id)
    service = TodoService(user=user)

    # Get overdue + today's todos properly
    overdue = service.get_overdue_todos().values('id', 'task', 'done', 'created_at')
    today = service.get_todos_for_today().values('id', 'task', 'done', 'created_at')

    todos = {
        "overdue": queryset_to_list(overdue),
        "today": queryset_to_list(today),
    }

    previous_result["todos"] = todos
    print(f"Fetched {len(todos['overdue'])} overdue + {len(todos['today'])} today todos")
    return previous_result


@shared_task
def fetch_daily_reminders(previous_result, user_id):
    user = User.objects.get(id=user_id)
    service = ReminderService(user=user)
    reminders_qs = service.get_upcoming_reminders()

    reminders = queryset_to_list(reminders_qs.values(
        'id', 'text', 'remind_at', 'completed', 'remind_at__date'
    ))

    previous_result["reminders"] = reminders
    print("Fetched reminders:", len(reminders))
    return previous_result


@shared_task
def fetch_daily_notes(previous_result, user_id):
    user = User.objects.get(id=user_id)
    service = NoteService(user=user)
    notes_qs = service.get_recent_notes(limit=5)  # optional: limit to recent ones

    notes = queryset_to_list(notes_qs.values('id', 'content', 'updated_at'))
    previous_result["notes"] = notes
    print("Fetched notes:", len(notes))
    return previous_result


@shared_task
def generate_summary_and_send(previous_result, user_id):
    clean_data = {
        "emails": previous_result.get("emails", []),
        "calendar": previous_result.get("calendar", []),
        "todos": previous_result.get("todos", {"overdue": [], "today": []}),
        "reminders": previous_result.get("reminders", []),
        "notes": previous_result.get("notes", []),
    }

    summary = generate_daily_summary(clean_data)
    send_whatsapp_text.delay(user_id=user_id, text=summary)
    return summary


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
    return f"Started daily summary for {users.count()} users"