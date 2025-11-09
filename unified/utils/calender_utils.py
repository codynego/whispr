from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import base64
import re
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from unified.utils.common_utils import is_message_important
from unified.models import ChannelAccount, Message, Conversation 
from unified.models import UserRule
from celery import shared_task
from google.auth.transport.requests import Request
from typing import List, Dict, Any
from django.db import transaction
from googleapiclient.errors import HttpError
from unified.models import CalendarEvent

logger = logging.getLogger(__name__)


# === Google Calendar Helpers ===
def parse_gcalendar_datetime(dt_str: str) -> datetime:
    """
    Parse Google Calendar datetime string to timezone-aware datetime.
    Handles both date and dateTime formats.
    """
    try:
        if 'T' in dt_str:
            # DateTime format: 2025-11-09T13:00:00+01:00
            parsed = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            # Date format: 2025-11-09
            parsed = datetime.fromisoformat(f"{dt_str}T00:00:00")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
    except Exception:
        return timezone.now()


def extract_event_details(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract key details from a Google Calendar event payload.
    """
    summary = event.get("summary", "")
    description = event.get("description", "")
    start = event.get("start", {})
    end = event.get("end", {})
    start_time = parse_gcalendar_datetime(start.get("dateTime") or start.get("date"))
    end_time = parse_gcalendar_datetime(end.get("dateTime") or end.get("date"))
    location = event.get("location", "")
    attendees = [a.get("email") for a in event.get("attendees", [])]
    status = event.get("status", "confirmed")
    organizer = event.get("organizer", {}).get("email")
    id = event.get("id")
    html_link = event.get("htmlLink")
    i_cal_uid = event.get("iCalUID")

    return {
        "external_id": id,
        "summary": summary,
        "description": description,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "attendees": attendees,
        "status": status,
        "organizer": organizer,
        "html_link": html_link,
        "i_cal_uid": i_cal_uid,
        "all_day": "date" in start,
    }


def fetch_calendar_events(account_id: int, days_ahead: int = 30) -> int:
    """
    Fetch Google Calendar events for the next N days.
    Does NOT store anything — passes data to Celery for storage.
    """
    print(f"DEBUG: Entering fetch_calendar_events with account_id={account_id}, days_ahead={days_ahead}")
    
    account = ChannelAccount.objects.get(id=account_id, is_active=True)
    print(f"DEBUG: Retrieved account {account.id} - {account.address_or_id}")
    
    logger.info(f"📅 Fetching Calendar events for {account.address_or_id}")

    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,  # Reuse Gmail creds for Calendar
        client_secret=settings.GMAIL_CLIENT_SECRET,
    )
    print(f"DEBUG: Created credentials object for account {account_id}")

    if not creds.valid and creds.refresh_token:
        print(f"DEBUG: Credentials invalid, refreshing for account {account_id}")
        creds.refresh(Request())
        account.access_token = creds.token
        account.save(update_fields=["access_token"])
        print(f"DEBUG: Refreshed and saved new access token for account {account_id}")

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    print(f"DEBUG: Built Calendar service for account {account_id}")

    # Time range: Now to N days ahead
    time_min = dj_timezone.now().isoformat() + 'Z'
    time_max = (dj_timezone.now() + timedelta(days=days_ahead)).isoformat() + 'Z'

    event_ids: List[str] = []
    full_events: List[Dict[str, Any]] = []
    
    try:
        # List events
        resp = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            maxResults=250  # Reasonable limit
        ).execute()
        print(f"DEBUG: List response keys: {list(resp.keys())}")
        events = resp.get("items", [])
        event_ids = [e["id"] for e in events]
        print(f"DEBUG: Extracted {len(event_ids)} event IDs: {event_ids[:3]}...")  # Truncate for log
        logger.info(f"Fetched {len(event_ids)} Calendar event IDs")

        # Fetch full details if needed (but list already has most; expand if required)
        for event in events:
            full_events.append(event)  # Use the list payload; fetch full if needed

        print(f"DEBUG: Total full_events collected: {len(full_events)}")
        
        if full_events:
            # Hand off to Celery for background storage
            print(f"DEBUG: Delaying store_calendar_events task with {len(full_events)} events")
            store_calendar_events(account_id, full_events)
            print(f"DEBUG: Task delayed successfully")
            return len(full_events)
        print(f"DEBUG: No full events to process, returning 0")
        return 0

    except HttpError as e:
        print(f"DEBUG: HTTP error in fetch: {e.resp.status} - {e.content}")
        logger.error(f"HTTP error fetching Calendar events: {e}")
        return 0
    except Exception as e:
        print(f"DEBUG: Exception in fetch: {type(e).__name__}: {e}")
        logger.error(f"Failed to fetch Calendar events: {e}")
        return 0


# ==============================================================
# ✅ Celery task: Store full Calendar events (no API calls)
# ==============================================================

@shared_task(name="store_calendar_events", bind=True)  # Add bind=True for self.retry if needed
def store_calendar_events(self, account_id: int, event_details_list: List[Dict[str, Any]]) -> None:
    start_time = time.time()
    print(f"DEBUG: Starting store_calendar_events_task for account {account_id} ({len(event_details_list)} events) at {start_time}")

    try:
        with transaction.atomic():  # Wrap whole task in atomic for rollback on failure
            account_start = time.time()
            account = ChannelAccount.objects.select_related("user").get(id=account_id, is_active=True)
            print(f"DEBUG: Account get took {time.time() - account_start:.2f}s")

            processed = 0
            for i, event_detail in enumerate(event_details_list, 1):
                event_start = time.time()
                event_id = event_detail.get("id")
                print(f"DEBUG: Processing event {i}/{len(event_details_list)} ({event_id}) at {time.time()}")

                # Extract details
                details = extract_event_details(event_detail)
                summary = details["summary"]
                description = details["description"]
                start_time = details["start_time"]
                end_time = details["end_time"]
                location = details["location"]
                attendees = details["attendees"]
                status = details["status"]
                organizer = details["organizer"]
                all_day = details["all_day"]
                print(f"DEBUG: Parsed event details for {event_id} - Summary: {summary[:50]}..., Start: {start_time}")

                # Assume CalendarEvent model (adapt to your schema)
                  # Adjust import
                event_op_start = time.time()
                try:
                    calendar_event, created = CalendarEvent.objects.update_or_create(
                        account=account,
                        external_id=event_id,
                        defaults={
                            "summary": summary,
                            "description": description,
                            "start_time": start_time,
                            "end_time": end_time,
                            "location": location,
                            "attendees": attendees,
                            "status": status,
                            "organizer": organizer,
                            "all_day": all_day,
                            "html_link": event_detail.get("htmlLink"),
                            "i_cal_uid": event_detail.get("iCalUID"),
                            "created_at": timezone.now(),
                            "updated_at": timezone.now(),
                        }
                    )
                    if created:
                        print(f"DEBUG: Created new CalendarEvent {event_id}")
                    else:
                        print(f"DEBUG: Updated existing CalendarEvent {event_id}")
                except Exception as e:
                    print(f"DEBUG: CalendarEvent {event_id} failed: {type(e).__name__}: {e}")
                    logger.error(f"Failed saving CalendarEvent {event_id}: {e}")
                    raise  # Re-raise to trigger atomic rollback
                print(f"DEBUG: CalendarEvent op took {time.time() - event_op_start:.2f}s")

                processed += 1
                if processed % 5 == 0:
                    print(f"DEBUG: {processed} events processed in {time.time() - start_time:.2f}s total")

            print(f"DEBUG: Task completed in {time.time() - start_time:.2f}s - Stored {processed} events")
    except Exception as e:
        print(f"DEBUG: Task failed after {time.time() - start_time:.2f}s: {type(e).__name__}: {e}")
        logger.error(f"Store task failed for {account_id}: {e}", exc_info=True)
        self.retry(countdown=60 * 5, exc=e)  # Retry after 5min


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
def create_calendar_event(self, account, summary, start_time, end_time=None, description="", location="", attendees=None, all_day=False):
    """Create a new Google Calendar event."""
    print("got to create_calendar_event")
    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
    )
    service = build("calendar", "v3", credentials=creds)

    # Parse times
    if all_day:
        start_dt = start_time.date().isoformat()
        end_dt = (start_time.date() + timedelta(days=1)).isoformat() if not end_time else end_time.date().isoformat()
        event_body = {
            "summary": summary,
            "description": description,
            "start": {"date": start_dt},
            "end": {"date": end_dt},
            "location": location,
            "attendees": [{"email": email} for email in (attendees or [])],
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]},
        }
    else:
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat() if end_time else (start_time + timedelta(hours=1)).isoformat()
        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso, "timeZone": start_time.tzinfo.zone if start_time.tzinfo else "UTC"},
            "end": {"dateTime": end_iso, "timeZone": end_time.tzinfo.zone if end_time and end_time.tzinfo else "UTC"},
            "location": location,
            "attendees": [{"email": email} for email in (attendees or [])],
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]},
        }

    try:
        created_event = service.events().insert(calendarId='primary', body=event_body).execute()
        logger.info(f"📅 Created Calendar event: {summary} at {start_time}")
        return created_event
    except HttpError as e:
        logger.error(f"⚠️ Failed to create Calendar event: {e.resp.status} - {e.content}")
        raise
    except Exception as e:
        logger.error(f"⚠️ Failed to create Calendar event: {e}")
        raise