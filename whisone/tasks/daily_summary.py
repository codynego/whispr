from celery import chain, shared_task
from datetime import datetime, timedelta
from whisone.services.gmail_service import GmailService
from whisone.services.calendar_service import GoogleCalendarService
from whisone.services.todo_service import TodoService
from whisone.services.note_service import NoteService
from whisone.services.reminder_service import ReminderService
from whatsapp.tasks import send_whatsapp_text
from .openai_client import generate_daily_summary
import openai
from django.conf import settings
import json
from whisone.models import Integration
from django.contrib.auth import get_user_model



User = get_user_model()


@shared_task
def fetch_daily_emails(user_id):
    user = User.objects.get(id=user_id)
    integration = Integration.objects.filter(user=user, provider="gmail").first()

    google_creds = {
        "client_id": settings.GMAIL_CLIENT_ID,
        "client_secret": settings.GMAIL_CLIENT_SECRET,
        "refresh_token": integration.refresh_token if integration else None,
        "access_token": integration.access_token if integration else None,
    }
    
    service = GmailService(**google_creds)
    emails = service.get_emails_last_24h()
    return {"emails": emails}


@shared_task
def fetch_daily_calendar(user_id, previous):
    user = User.objects.get(id=user_id)
    integration = Integration.objects.filter(user=user, provider="google_calendar").first()

    google_creds = {
        "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
        "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
        "refresh_token": integration.refresh_token if integration else None,
        "access_token": integration.access_token if integration else None,
    }

    service = GoogleCalendarService(**google_creds)
    events = service.get_events_for_today()
    previous["calendar"] = events
    return previous


@shared_task
def fetch_daily_todos(user_id, previous):
    user = User.objects.get(id=user_id)
    service = TodoService(user=user)
    todos = service.get_todos_for_today()
    previous["todos"] = todos
    return previous


@shared_task
def fetch_daily_reminders(user_id, previous):
    user = User.objects.get(id=user_id)
    service = ReminderService(user=user)
    reminders = service.get_upcoming_reminders()
    previous["reminders"] = reminders
    return previous


@shared_task
def fetch_daily_notes(user_id, previous):
    user = User.objects.get(id=user_id)
    service = NoteService(user=user)
    notes = service.get_recent_notes()
    previous["notes"] = notes
    return previous


@shared_task
def generate_summary_and_send(user_id, data):
    summary = generate_daily_summary(data)
    send_whatsapp_text(user_id, summary, alert_type="daily_summary")
    return summary



def run_daily_summary():
    users = User.objects.all()

    # Create a chain for each user
    user_chains = [
        chain(
            fetch_daily_emails.s(user.id),
            fetch_daily_calendar.s(user.id),
            fetch_daily_todos.s(user.id),
            fetch_daily_reminders.s(user.id),
            fetch_daily_notes.s(user.id),
            generate_summary_and_send.s(user.id)
        )
        for user in users
    ]

    # Run all user chains in parallel
    group(user_chains).delay()