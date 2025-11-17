from typing import List, Dict, Any, Optional
from datetime import datetime
import inspect
import json
from django.utils import timezone
import email.utils

# Services
from .services.gmail_service import GmailService
from .services.calendar_service import GoogleCalendarService
from .services.note_service import NoteService
from .services.reminder_service import ReminderService
from .services.todo_service import TodoService
from .task_frame_builder import TaskFrameBuilder
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Executor:
    """
    Executor that always uses live data (no knowledge vault caching for fetchable actions).
    Supports: emails, calendar events, notes, reminders, todos.
    """

    FETCH_ACTIONS = {"fetch_emails", "fetch_events", "fetch_todos", "fetch_notes", "fetch_reminders"}

    def __init__(self, user: User, gmail_creds=None, calendar_creds=None):
        self.user = user

        # Services
        self.note_service = NoteService(user)
        self.reminder_service = ReminderService(user)
        self.todo_service = TodoService(user)
        self.task_builder = TaskFrameBuilder()

        self.gmail_service = GmailService(**gmail_creds) if gmail_creds else None
        self.calendar_service = GoogleCalendarService(**calendar_creds) if calendar_creds else None

    # -------------------------
    # UTILITY FUNCTIONS
    # -------------------------
    def _safe_call(self, func, params: Dict[str, Any]):
        sig = inspect.signature(func)
        allowed = {k: v for k, v in params.items() if k in sig.parameters}
        return func(**allowed)

    def _parse_datetime(self, value: Optional[str]):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    # -------------------------
    # MAIN EXECUTION
    # -------------------------
    def execute_task_frames(self, task_frames: List[Dict[str, Any]]):
        results = []

        for frame in task_frames:
            action = frame.get("action")
            params = frame.get("parameters", {})

            if not frame.get("ready", False):
                results.append({
                    "action": action,
                    "ready": False,
                    "missing_fields": frame.get("missing_fields", [])
                })
                continue

            try:
                result = self._execute_single_action(action, params)
                results.append({"action": action, "ready": True, "result": result})
            except Exception as e:
                results.append({"action": action, "ready": True, "error": str(e)})

        return results

    # -------------------------
    # SINGLE ACTION EXECUTION
    # -------------------------
    def _execute_single_action(self, action: str, params: Dict[str, Any]):
        # -------- NOTES --------
        if action == "create_note":
            note = self._safe_call(self.note_service.create_note, {"content": params.get("content")})
            return {"id": note.id, "content": note.content, "created_at": note.created_at.isoformat()}

        elif action == "update_note":
            note = self._safe_call(self.note_service.update_note, {
                "note_id": params.get("note_id"),
                "new_content": params.get("content")
            })
            return {"id": note.id, "content": note.content, "created_at": note.created_at.isoformat()} if note else None

        elif action == "delete_note":
            return self._safe_call(self.note_service.delete_note, {"note_id": params.get("note_id")})

        elif action == "fetch_notes":
            notes_qs = self._safe_call(self.note_service.fetch_notes, {"filters": params.get("filters", [])})
            return [{"id": n.id, "content": n.content, "created_at": n.created_at.isoformat()} for n in notes_qs]

        # -------- REMINDERS --------
        elif action == "create_reminder":
            reminder = self._safe_call(self.reminder_service.create_reminder, {
                "text": params.get("text"),
                "remind_at": self._parse_datetime(params.get("remind_at"))
            })
            return {"id": reminder.id, "text": reminder.text, "remind_at": reminder.remind_at.isoformat()}

        elif action == "update_reminder":
            reminder = self._safe_call(self.reminder_service.update_reminder, {
                "reminder_id": params.get("reminder_id"),
                "text": params.get("text"),
                "remind_at": self._parse_datetime(params.get("remind_at"))
            })
            return {"id": reminder.id, "text": reminder.text, "remind_at": reminder.remind_at.isoformat()} if reminder else None

        elif action == "delete_reminder":
            return self._safe_call(self.reminder_service.delete_reminder, {"reminder_id": params.get("reminder_id")})

        elif action == "fetch_reminders":
            reminders_qs = self._safe_call(self.reminder_service.fetch_reminders, {"filters": params.get("filters", [])})
            return [{"id": r.id, "text": r.text, "remind_at": r.remind_at.isoformat()} for r in reminders_qs]

        # -------- TODOS --------
        elif action == "create_todo":
            todo = self._safe_call(self.todo_service.create_todo, {"task": params.get("task")})
            return {"id": todo.id, "task": todo.task, "done": todo.done}

        elif action == "update_todo":
            todo = self._safe_call(self.todo_service.update_todo, {
                "todo_id": params.get("todo_id"),
                "task": params.get("task"),
                "done": params.get("done")
            })
            return {"id": todo.id, "task": todo.task, "done": todo.done} if todo else None

        elif action == "delete_todo":
            return self._safe_call(self.todo_service.delete_todo, {"todo_id": params.get("todo_id")})

        elif action == "fetch_todos":
            todos_qs = self._safe_call(self.todo_service.fetch_todos, {"filters": params.get("filters", [])})
            return [{"id": t.id, "task": t.task, "done": t.done} for t in todos_qs]

        # -------- EMAILS --------
        elif action == "fetch_emails" and self.gmail_service:
            filters = params.get("filters", [])
            query = ""
            after = before = None
            unread_only = False
            max_results = params.get("max_results", 20)

            for f in filters:
                if isinstance(f, dict):
                    # Handle filters as {filter_type: value} e.g., {'from': 'alx'}
                    for filter_key, filter_value in f.items():
                        key = filter_key.lower()
                        value = filter_value
                        if key == "keyword": query += f" {value}"
                        elif key == "from": query += f" from:{value}"
                        elif key == "to": query += f" to:{value}"
                        elif key == "subject": query += f" subject:{value}"
                        elif key == "unread": unread_only = bool(value)
                        elif key == "after": after = self._parse_datetime(value)
                        elif key == "before": before = self._parse_datetime(value)
                elif isinstance(f, dict) and "key" in f and "value" in f:
                    # Backward compatibility: Handle {'key': 'from', 'value': 'alx'}
                    key = f.get("key", "").lower()
                    value = f.get("value", "")
                    if key == "keyword": query += f" {value}"
                    elif key == "from": query += f" from:{value}"
                    elif key == "to": query += f" to:{value}"
                    elif key == "subject": query += f" subject:{value}"
                    elif key == "unread": unread_only = bool(value)
                    elif key == "after": after = self._parse_datetime(value)
                    elif key == "before": before = self._parse_datetime(value)

            emails = self._safe_call(self.gmail_service.fetch_emails, {
                "query": query.strip(),
                "after": after,
                "before": before,
                "unread_only": unread_only,
                "max_results": max_results
            })

            result = []
            for e in emails:
                received_at = None
                if e.get("date"):
                    try:
                        received_at = email.utils.parsedate_to_datetime(e["date"]).isoformat()
                    except Exception:
                        received_at = None

                result.append({
                    "id": e.get("id"),
                    "subject": e.get("subject"),
                    "from": e.get("from"),
                    "to": e.get("to"),
                    "snippet": e.get("snippet"),
                    "received_at": received_at,
                    "unread": e.get("unread", False)
                })
            return result

        elif action == "mark_email_read" and self.gmail_service:
            self._safe_call(self.gmail_service.mark_as_read, {"msg_id": params.get("email_id")})
            return True

        elif action == "mark_email_unread" and self.gmail_service:
            self._safe_call(self.gmail_service.mark_as_unread, {"msg_id": params.get("email_id")})
            return True

        # -------- CALENDAR --------
        elif action in {"fetch_events", "create_event", "update_event"} and self.calendar_service:
            ev_result = self._safe_call(getattr(self.calendar_service, action), {
                "event_id": params.get("event_id"),
                "summary": params.get("summary"),
                "description": params.get("description"),
                "start_time": self._parse_datetime(params.get("start_time")),
                "end_time": self._parse_datetime(params.get("end_time")),
                "attendees": params.get("attendees", []),
                "timezone": params.get("timezone"),
                "filters": params.get("filters", []),
                "max_results": params.get("max_results", 10)
            })
            return ev_result

        elif action == "delete_event" and self.calendar_service:
            return self._safe_call(self.calendar_service.delete_event, {"event_id": params.get("event_id")})

        else:
            return {"error": f"Unknown action or missing service for {action}"}

