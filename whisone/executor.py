from typing import List, Dict, Any
from datetime import datetime, timedelta
import inspect

# Import Services
from .services.gmail_service import GmailService
from .services.calendar_service import GoogleCalendarService
from .services.note_service import NoteService
from .services.reminder_service import ReminderService
from .services.todo_service import TodoService


class Executor:
    def __init__(self, user, gmail_creds=None, calendar_creds=None):
        self.user = user

        # Local services
        self.note_service = NoteService(user)
        self.reminder_service = ReminderService(user)
        self.todo_service = TodoService(user)

        # External API services
        self.gmail_service = GmailService(**gmail_creds) if gmail_creds else None
        self.calendar_service = GoogleCalendarService(**calendar_creds) if calendar_creds else None

    def _safe_call(self, func, params: Dict[str, Any]):
        """
        Safely call any function using only allowed params.
        Avoids TypeErrors from unexpected keyword arguments.
        """
        sig = inspect.signature(func)
        allowed = {k: v for k, v in params.items() if k in sig.parameters}
        return func(**allowed)

    def _parse_datetime(self, value: str) -> datetime:
        """
        Safely convert ISO8601 string → datetime object.
        Returns None if invalid or empty.
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    def execute_task(self, task_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []

        for step in task_plan:
            action = step.get("action")
            params = step.get("params", {})

            try:
                # -------------------------
                # NOTES
                # -------------------------
                if action == "create_note":
                    mapped = {"content": params.get("content", "")}
                    note = self._safe_call(self.note_service.create_note, mapped)
                    results.append({"action": action, "result": {"id": note.id, "content": note.content}})

                elif action == "update_note":
                    mapped = {
                        "note_id": params.get("note_id"),
                        "content": params.get("content", "")
                    }
                    note = self._safe_call(self.note_service.update_note, mapped)
                    results.append({"action": action, "result": note})

                elif action == "delete_note":
                    mapped = {"note_id": params.get("note_id")}
                    ok = self._safe_call(self.note_service.delete_note, mapped)
                    results.append({"action": action, "result": ok})

                # -------------------------
                # REMINDERS
                # -------------------------
                elif action == "create_reminder":
                    remind_at = self._parse_datetime(params.get("datetime"))
                    mapped = {
                        "text": params.get("title", ""),
                        "remind_at": remind_at,
                    }
                    reminder = self._safe_call(self.reminder_service.create_reminder, mapped)
                    results.append({"action": action, "result": {"id": reminder.id, "text": reminder.text}})

                elif action == "update_reminder":
                    remind_at = self._parse_datetime(params.get("datetime"))
                    mapped = {
                        "reminder_id": params.get("reminder_id"),
                        "text": params.get("title", ""),
                        "remind_at": remind_at,
                    }
                    reminder = self._safe_call(self.reminder_service.update_reminder, mapped)
                    results.append({"action": action, "result": reminder})

                elif action == "delete_reminder":
                    mapped = {"reminder_id": params.get("reminder_id")}
                    ok = self._safe_call(self.reminder_service.delete_reminder, mapped)
                    results.append({"action": action, "result": ok})

                # -------------------------
                # TODOS
                # -------------------------
                elif action == "add_todo":
                    mapped = {"task": params.get("task", "")}
                    todo = self._safe_call(self.todo_service.add_todo, mapped)
                    results.append({"action": action, "result": {"id": todo.id, "task": todo.task}})

                elif action == "update_todo":
                    mapped = {
                        "todo_id": params.get("todo_id"),
                        "task": params.get("task"),
                        "done": params.get("done")
                    }
                    todo = self._safe_call(self.todo_service.update_todo, mapped)
                    results.append({"action": action, "result": todo})

                elif action == "delete_todo":
                    mapped = {"todo_id": params.get("todo_id")}
                    ok = self._safe_call(self.todo_service.delete_todo, mapped)
                    results.append({"action": action, "result": ok})

                # -------------------------
                # GMAIL
                # -------------------------
                elif action == "fetch_emails" and self.gmail_service:
                    emails = self._safe_call(self.gmail_service.fetch_emails, params)
                    results.append({"action": action, "result": emails})

                elif action == "mark_email_read" and self.gmail_service:
                    self._safe_call(self.gmail_service.mark_as_read, params)
                    results.append({"action": action, "result": True})

                # -------------------------
                # CALENDAR
                # -------------------------
                elif action == "fetch_events" and self.calendar_service:
                    # Convert time_min and time_max into proper datetime objects
                    if "time_min" in params:
                        params["time_min"] = self._parse_datetime(params["time_min"])
                    if "time_max" in params:
                        params["time_max"] = self._parse_datetime(params["time_max"])

                    events = self._safe_call(self.calendar_service.fetch_events, params)
                    results.append({"action": action, "result": events})

                elif action == "create_event" and self.calendar_service:
                    # Ensure datetime
                    start_time = self._parse_datetime(params.get("start_time"))
                    if start_time:
                        params["start_time"] = start_time
                    event = self._safe_call(self.calendar_service.create_event, params)
                    results.append({"action": action, "result": event})

                elif action == "update_event" and self.calendar_service:
                    start_time = self._parse_datetime(params.get("start_time"))
                    if start_time:
                        params["start_time"] = start_time
                    event = self._safe_call(self.calendar_service.update_event, params)
                    results.append({"action": action, "result": event})

                elif action == "delete_event" and self.calendar_service:
                    ok = self._safe_call(self.calendar_service.delete_event, params)
                    results.append({"action": action, "result": ok})

                else:
                    results.append({"action": action, "result": "Unknown action or service not initialized"})

            except Exception as e:
                results.append({"action": action, "error": str(e)})

        return results
