from typing import List, Dict, Any
from datetime import datetime
import inspect

# Import Services
from .services.gmail_service import GmailService
from .services.calendar_service import GoogleCalendarService
from .services.note_service import NoteService
from .services.reminder_service import ReminderService
from .services.todo_service import TodoService


class Executor:
    """
    Executes all structured tasks produced by TaskPlanner.
    Now supports:
    - Filters for Gmail, Calendar, Notes, Todos, Reminders
    - Strict safe param passing
    - ISO datetime parsing
    """

    FETCH_ACTIONS = {
        "fetch_emails",
        "fetch_events",
        "fetch_todos",
        "fetch_notes",
        "fetch_reminders",
    }

    def __init__(self, user, gmail_creds=None, calendar_creds=None):
        self.user = user

        # Local storage services
        self.note_service = NoteService(user)
        self.reminder_service = ReminderService(user)
        self.todo_service = TodoService(user)

        # External API services
        self.gmail_service = GmailService(**gmail_creds) if gmail_creds else None
        self.calendar_service = GoogleCalendarService(**calendar_creds) if calendar_creds else None

    # ---------------------------------------------------------------------
    # Safe function call
    # ---------------------------------------------------------------------
    def _safe_call(self, func, params: Dict[str, Any]):
        """
        Safely call a service function with ONLY allowed params.
        Avoids runtime crashes caused by extra or unexpected params.
        """
        sig = inspect.signature(func)
        allowed = {k: v for k, v in params.items() if k in sig.parameters}
        return func(**allowed)

    # ---------------------------------------------------------------------
    # Datetime parsing
    # ---------------------------------------------------------------------
    def _parse_datetime(self, value: str):
        """
        Convert ISO8601 string → datetime object.
        Returns None if invalid.
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except:
            return None

    # ---------------------------------------------------------------------
    # EXECUTE TASKS
    # ---------------------------------------------------------------------
    def execute_task(self, task_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []

        for step in task_plan:
            action = step.get("action")
            params = step.get("params", {})

            try:
                # =============================================================
                # NOTES
                # =============================================================
                if action == "create_note":
                    mapped = {"content": params.get("content")}
                    note = self._safe_call(self.note_service.create_note, mapped)
                    results.append({"action": action, "result": {"id": note.id, "content": note.content}})

                elif action == "update_note":
                    mapped = {
                        "note_id": params.get("note_id"),
                        "content": params.get("content")
                    }
                    note = self._safe_call(self.note_service.update_note, mapped)
                    results.append({"action": action, "result": note})

                elif action == "delete_note":
                    mapped = {"note_id": params.get("note_id")}
                    ok = self._safe_call(self.note_service.delete_note, mapped)
                    results.append({"action": action, "result": ok})

                elif action == "fetch_notes":
                    mapped = {
                        "filters": params.get("filters", []),
                    }
                    notes = self._safe_call(self.note_service.fetch_notes, mapped)
                    results.append({"action": action, "result": notes})

                # =============================================================
                # REMINDERS
                # =============================================================
                elif action == "create_reminder":
                    mapped = {
                        "text": params.get("title"),
                        "remind_at": self._parse_datetime(params.get("datetime")),
                    }
                    reminder = self._safe_call(self.reminder_service.create_reminder, mapped)
                    results.append({"action": action, "result": {"id": reminder.id, "text": reminder.text}})

                elif action == "update_reminder":
                    mapped = {
                        "reminder_id": params.get("reminder_id"),
                        "text": params.get("title"),
                        "remind_at": self._parse_datetime(params.get("datetime")),
                    }
                    reminder = self._safe_call(self.reminder_service.update_reminder, mapped)
                    results.append({"action": action, "result": reminder})

                elif action == "delete_reminder":
                    mapped = {"reminder_id": params.get("reminder_id")}
                    ok = self._safe_call(self.reminder_service.delete_reminder, mapped)
                    results.append({"action": action, "result": ok})

                elif action == "fetch_reminders":
                    mapped = {"filters": params.get("filters", [])}
                    reminders = self._safe_call(self.reminder_service.fetch_reminders, mapped)
                    results.append({"action": action, "result": reminders})

                # =============================================================
                # TODOS
                # =============================================================
                elif action == "add_todo":
                    mapped = {"task": params.get("task")}
                    todo = self._safe_call(self.todo_service.add_todo, mapped)
                    results.append({"action": action, "result": {"id": todo.id, "task": todo.task}})

                elif action == "update_todo":
                    mapped = {
                        "todo_id": params.get("todo_id"),
                        "task": params.get("task"),
                        "done": params.get("done"),
                    }
                    todo = self._safe_call(self.todo_service.update_todo, mapped)
                    results.append({"action": action, "result": todo})

                elif action == "delete_todo":
                    mapped = {"todo_id": params.get("todo_id")}
                    ok = self._safe_call(self.todo_service.delete_todo, mapped)
                    results.append({"action": action, "result": ok})

                elif action == "fetch_todos":
                    mapped = {"filters": params.get("filters", [])}
                    todos = self._safe_call(self.todo_service.fetch_todos, mapped)
                    results.append({"action": action, "result": todos})

                # =============================================================
                # GMAIL (search supported)
                # =============================================================
                elif action == "fetch_emails" and self.gmail_service:
                    # Extract filters from task params
                    filters = params.get("filters", [])

                    # Defaults
                    query = ""
                    after = None
                    before = None
                    unread_only = False
                    max_results = params.get("max_results", 20)

                    # Parse filters
                    for f in filters:
                        key = f.get("key", "").lower()
                        value = f.get("value", "")
                        if key == "keyword":
                            query += f" {value}"
                        elif key == "from":
                            query += f" from:{value}"
                        elif key == "to":
                            query += f" to:{value}"
                        elif key == "subject":
                            query += f" subject:{value}"
                        elif key == "unread":
                            unread_only = bool(value)
                        elif key == "after":
                            after = datetime.fromisoformat(value)
                        elif key == "before":
                            before = datetime.fromisoformat(value)

                    emails = self._safe_call(self.gmail_service.fetch_emails, {
                        "query": query.strip(),
                        "after": after,
                        "before": before,
                        "unread_only": unread_only,
                        "max_results": max_results
                    })

                    results.append({"action": action, "result": emails})

                elif action == "mark_email_read" and self.gmail_service:
                    mapped = {"email_id": params.get("email_id")}
                    self._safe_call(self.gmail_service.mark_as_read, mapped)
                    results.append({"action": action, "result": True})

                # =============================================================
                # CALENDAR (with search filters)
                # =============================================================
                elif action == "fetch_events" and self.calendar_service:
                    mapped = {
                        "time_min": self._parse_datetime(params.get("time_min")),
                        "time_max": self._parse_datetime(params.get("time_max")),
                        "filters": params.get("filters", []),
                        "max_results": params.get("max_results", 10),
                    }
                    events = self._safe_call(self.calendar_service.fetch_events, mapped)
                    results.append({"action": action, "result": events})

                elif action == "create_event" and self.calendar_service:
                    mapped = {
                        "summary": params.get("summary"),
                        "start_time": self._parse_datetime(params.get("start_time")),
                    }
                    event = self._safe_call(self.calendar_service.create_event, mapped)
                    results.append({"action": action, "result": event})

                elif action == "update_event" and self.calendar_service:
                    mapped = {
                        "event_id": params.get("event_id"),
                        "summary": params.get("summary"),
                        "start_time": self._parse_datetime(params.get("start_time")),
                    }
                    event = self._safe_call(self.calendar_service.update_event, mapped)
                    results.append({"action": action, "result": event})

                elif action == "delete_event" and self.calendar_service:
                    mapped = {"event_id": params.get("event_id")}
                    ok = self._safe_call(self.calendar_service.delete_event, mapped)
                    results.append({"action": action, "result": ok})

                # =============================================================
                # UNKNOWN ACTION
                # =============================================================
                else:
                    results.append({"action": action, "result": "Unknown action or missing service"})

            except Exception as e:
                results.append({"action": action, "error": str(e)})

        return results
