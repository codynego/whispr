from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class GoogleCalendarService:
    def __init__(self, access_token: str, refresh_token: str, client_id: str, client_secret: str):
        """Initialize Google Calendar API service."""
        self.creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        self.service = build('calendar', 'v3', credentials=self.creds)

    # -----------------------------
    # Create event
    # -----------------------------
    def create_event(
        self,
        summary: str,
        description: str = "",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        attendees: Optional[List[str]] = None,
        timezone: str = "UTC"
    ) -> Dict:
        start_time = start_time or datetime.utcnow()
        end_time = end_time or (start_time + timedelta(hours=1))

        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': timezone},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': timezone},
        }
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        created_event = self.service.events().insert(calendarId='primary', body=event).execute()
        return {
            "id": created_event['id'],
            "summary": created_event.get('summary'),
            "start": created_event['start'],
            "end": created_event['end']
        }

    # -----------------------------
    # Update event
    # -----------------------------
    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        attendees: Optional[List[str]] = None
    ) -> Dict:
        event = self.service.events().get(calendarId='primary', eventId=event_id).execute()

        if summary:
            event['summary'] = summary
        if description:
            event['description'] = description
        if start_time:
            event['start']['dateTime'] = start_time.isoformat()
        if end_time:
            event['end']['dateTime'] = end_time.isoformat()
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        updated_event = self.service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
        return {
            "id": updated_event['id'],
            "summary": updated_event.get('summary'),
            "start": updated_event['start'],
            "end": updated_event['end']
        }

    # -----------------------------
    # Delete event
    # -----------------------------
    def delete_event(self, event_id: str) -> bool:
        self.service.events().delete(calendarId='primary', eventId=event_id).execute()
        return True

    # -----------------------------
    # Fetch events
    # -----------------------------
    def fetch_events(
        self,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """Fetch events from Google Calendar within a time range."""
        time_min = time_min or datetime.utcnow()
        time_max = time_max or (time_min + timedelta(days=7))

        events_result = self.service.events().list(
            calendarId='primary',
            timeMin=time_min.isoformat() + 'Z',
            timeMax=time_max.isoformat() + 'Z',
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = []
        for event in events_result.get('items', []):
            events.append({
                "id": event['id'],
                "summary": event.get('summary'),
                "description": event.get('description'),
                "start": event['start'],
                "end": event['end'],
                "attendees": [a.get('email') for a in event.get('attendees', [])] if event.get('attendees') else []
            })
        return events

    def get_events_for_today(self, max_results: int = 50) -> List[Dict]:
        """
        Fetch all events happening today (from 00:00 to 23:59 in UTC).
        """
        now = datetime.utcnow()
        start_of_day = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
        end_of_day = datetime.combine(now.date(), datetime.max.time(), tzinfo=timezone.utc)

        return self.fetch_events(time_min=start_of_day, time_max=end_of_day, max_results=max_results)