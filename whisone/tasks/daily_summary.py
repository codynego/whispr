from celery import chain, shared_task, group
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model

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


# First task in the chain – only receives user_id
@shared_task
def fetch_daily_emails(user_id):
    user = User.objects.get(id=user_id)
    integration = Integration.objects.filter(user=user, provider="gmail").first()

    if not integration:
        return {"emails": [], "user_id": user_id}

    google_creds = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": integration.refresh_token,
        "access_token": integration.access_token,
        "user_email": user.email,
    }

    service = GmailService(**google_creds)
    emails = service.get_emails_last_24h()
    return {"emails": emails, "user_id": user_id}


# All subsequent tasks receive (previous_result, user_id)
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
        events = service.get_events_for_today()

    previous_result["calendar"] = events
    return previous_result


@shared_task
def fetch_daily_todos(previous_result, user_id):
    user = User.objects.get(id=user_id)
    service = TodoService(user=user)
    previous_result["todos"] = service.get_todos_for_today()
    return previous_result


@shared_task
def fetch_daily_reminders(previous_result, user_id):
    user = User.objects.get(id=user_id)
    service = ReminderService(user=user)
    previous_result["reminders"] = service.get_upcoming_reminders()
    return previous_result


@shared_task
def fetch_daily_notes(previous_result, user_id):
    user = User.objects.get(id=user_id)
    service = NoteService(user=user)
    previous_result["notes"] = service.get_recent_notes()
    return previous_result


@shared_task
def generate_summary_and_send(previous_result, user_id):
    # Remove user_id from the dict if it somehow got in the way (optional)
    data_for_summary = {k: v for k, v in previous_result.items() if k != "user_id"}

    summary = generate_daily_summary(data_for_summary)
    send_whatsapp_text.delay(user_id, summary, alert_type="daily_summary")
    return summary


# Main entry point – run once per day (via celery beat or management command)
@shared_task
def run_daily_summary():
    users = User.objects.filter(is_active=True)  # optionally filter only active users

    if not users.exists():
        return "No users to process"

    chains = []
    for user in users:
        user_id = user.id

        user_chain = chain(
            fetch_daily_emails.s(user_id),                   # returns dict + user_id inside
            fetch_daily_calendar.s(user_id),
            fetch_daily_todos.s(user_id),
            fetch_daily_reminders.s(user_id),
            fetch_daily_notes.s(user_id),
            generate_summary_and_send.s(user_id),
        )
        chains.append(user_chain)

    # Execute all user chains in parallel
    group(chains).apply_async()

    return f"Started daily summary for {users.count()} users"