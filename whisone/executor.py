from typing import List, Dict, Any, Optional
from datetime import datetime
import inspect
import email.utils
import logging
from dateutil.parser import parse as parse_dt
from django.contrib.auth import get_user_model
from datetime import timezone

# Services
from .services.gmail_service import GmailService
from .services.calendar_service import GoogleCalendarService
from .services.note_service import NoteService
from .services.reminder_service import ReminderService
from .services.todo_service import TodoService
from .task_frame_builder import TaskFrameBuilder
# from .knowledge_vault_manager import KnowledgeVaultManager
from .memory_querier import MemoryQueryManager

User = get_user_model()
logger = logging.getLogger(__name__)


class Executor:
    """
    Executor that handles all ready task frames.
    Supports: emails, calendar events, notes, reminders, todos, and general queries.
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

        # Knowledge Vault
        self.vault_manager = KVQueryManager(user)

    # -------------------------
    # UTILITY FUNCTIONS
    # -------------------------
    def _safe_call(self, func, params: Dict[str, Any]):
        sig = inspect.signature(func)
        allowed = {k: v for k, v in params.items() if k in sig.parameters}
        try:
            return func(**allowed) if allowed else func()
        except Exception as e:
            logger.error(f"Error calling function {func.__name__} with params {allowed}: {e}")
            return None

    def _parse_datetime(self, value: Optional[str]):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            try:
                return parse_dt(value)
            except Exception:
                return None

    # -------------------------
    # MAIN EXECUTION
    # -------------------------
    def execute_task_frames(self, task_frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Executes all task frames and returns a consistent result list.
        Every frame gets a response — success, validation error, or execution error.
        """
        results = []

        for i, frame in enumerate(task_frames):
            action = frame.get("action", "unknown_action")
            intent = frame.get("intent", "No intent provided")
            params = frame.get("parameters", {})

            # === 1. Not ready → validation failure ===
            if not frame.get("ready", False):
                missing = frame.get("missing_fields", [])
                error_msg = f"Missing required fields: {', '.join(missing)}" if missing else "Task not ready"
                results.append({
                    "index": i,
                    "intent": intent,
                    "action": action,
                    "ready": False,
                    "error": error_msg,
                    "missing_fields": missing,
                    "parameters": params,
                })
                continue

            # === 2. Ready → try to execute ===
            try:
                result = self._execute_single_action(action, params)

                results.append({
                    "index": i,
                    "intent": intent,
                    "action": action,
                    "ready": True,
                    "success": True,
                    "result": result,
                    "parameters": params,
                })

            except Exception as e:
                import traceback
                error_detail = str(e)
                tb = traceback.format_exc()

                logger.error(f"Execution failed for action '{action}' (intent: {intent})\n"
                             f"Params: {params}\n"
                             f"Error: {error_detail}\n"
                             f"Traceback: {tb}")

                results.append({
                    "index": i,
                    "intent": intent,
                    "action": action,
                    "ready": True,
                    "success": False,
                    "error": error_detail,
                    "error_type": type(e).__name__,
                    "parameters": params,
                    "traceback": tb.splitlines()[-5:],  # last 5 lines for context
                })

        return results

    # -------------------------
    # SINGLE ACTION EXECUTION
    # -------------------------
    def _execute_single_action(self, action: str, params: Dict[str, Any]):
        # -------- NOTES --------
        if action == "create_note":
            note = self._safe_call(self.note_service.create_note, {"content": params.get("content") or params.get("text") or params.get("intent")})
            return {"id": note.id, "content": note.content, "created_at": note.created_at.isoformat()}

        elif action == "update_note":
            note = self._safe_call(self.note_service.update_note, {
                "note_id": params.get("note_id"),
                "new_content": params.get("content") or params.get("text") or params.get("intent")
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
                "text": params.get("text") or params.get("intent"),
                "remind_at": self._parse_datetime(params.get("remind_at"))
            })
            return {"id": reminder.id, "text": reminder.text, "remind_at": reminder.remind_at.isoformat()}

        elif action == "update_reminder":
            reminder = self._safe_call(self.reminder_service.update_reminder, {
                "reminder_id": params.get("reminder_id"),
                "text": params.get("text") or params.get("intent"),
                "remind_at": self._parse_datetime(params.get("remind_at"))
            })
            return {"id": reminder.id, "text": reminder.text, "remind_at": reminder.remind_at.isoformat()} if reminder else None

        elif action == "delete_reminder":
            return self._safe_call(self.reminder_service.delete_reminder, {"reminder_id": params.get("reminder_id")})

        elif action == "fetch_reminders":
            filters_list = params.get("filters", [])
            if params.get("time_min"):
                filters_list.append({"key": "after", "value": self._parse_datetime(params['time_min'])})
            if params.get("time_max"):
                filters_list.append({"key": "before", "value": self._parse_datetime(params['time_max'])})
            processed_filters = [f for f in filters_list if isinstance(f, dict) and "key" in f and "value" in f and f["value"] is not None]
            reminders_qs = self._safe_call(self.reminder_service.fetch_reminders, {"filters": processed_filters})
            return [{"id": r.id, "text": r.text, "remind_at": r.remind_at.isoformat(), "completed": r.completed} for r in reminders_qs]

        # -------- TODOS --------
        elif action == "create_todo":
            todo = self._safe_call(self.todo_service.create_todo, {"task": params.get("task") or params.get("intent")})
            return {"id": todo.id, "task": todo.task, "done": todo.done}

        elif action == "update_todo":
            # ← ADD THIS BLOCK
            if params.get("status") in ("completed", "done", "yes", True):
                params["done"] = True
            elif params.get("status") in ("pending", "incomplete", False):
                params["done"] = False
            # ← END

            todo = self._safe_call(self.todo_service.update_todo, {
                "todo_id": params.get("todo_id"),
                "task": params.get("task"),
                "done": params.get("done")
            })

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
                    for key, value in f.items():
                        key = key.lower()
                        if key == "keyword": query += f" {value}"
                        elif key == "from": query += f" from:{value}"
                        elif key == "to": query += f" to:{value}"
                        elif key == "subject": query += f" subject:{value}"
                        elif key == "unread": unread_only = bool(value)
                        elif key == "after": after = self._parse_datetime(value)
                        elif key == "before": before = self._parse_datetime(value)

            query = " ".join(query.split())  # Clean up spaces
            emails = self._safe_call(self.gmail_service.fetch_emails, {
                "query": query,
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

        elif action in {"mark_email_read", "mark_email_unread"} and self.gmail_service:
            func = self.gmail_service.mark_as_read if action == "mark_email_read" else self.gmail_service.mark_as_unread
            self._safe_call(func, {"msg_id": params.get("email_id")})
            return True

        # -------- CALENDAR --------
        elif action in {"fetch_events", "create_event", "update_event"} and self.calendar_service:
            start_time = self._parse_datetime(params.get("start_time"))
            end_time = self._parse_datetime(params.get("end_time"))

            # Ensure timezone
            if start_time and start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time and end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            ev_result = self._safe_call(getattr(self.calendar_service, action), {
                "event_id": params.get("event_id"),
                "summary": params.get("summary") or params.get("intent"),
                "description": params.get("description") or params.get("intent"),
                "start_time": start_time,
                "end_time": end_time,
                "attendees": params.get("attendees", []),
                "timezone": params.get("timezone") or "UTC",
                "filters": params.get("filters", []),
                "max_results": params.get("max_results", 10)
            })
            return ev_result

        elif action == "delete_event" and self.calendar_service:
            return self._safe_call(self.calendar_service.delete_event, {"event_id": params.get("event_id")})

        # -------- GENERAL QUERY --------
        elif action == "general_query":
            entity_type = params.get("entity_type")
            topic = params.get("topic")
            time_range = params.get("time_range", {})
            filters = params.get("filters", [])

            query_filters = []

            if "start" in time_range:
                start = self._parse_datetime(time_range["start"])
                if start: query_filters.append({"key": "after", "value": start})
            if "end" in time_range:
                end = self._parse_datetime(time_range["end"])
                if end: query_filters.append({"key": "before", "value": end})

            

            for f in filters:
                if isinstance(f, dict) and "key" in f and "value" in f and f["value"] is not None:
                    query_filters.append(f)


            vault_results = self.vault_manager.query(
                keyword=topic,
                limit=5
            )
            return {"results": vault_results}

        else:
            logger.warning(f"No service or unknown action for '{action}'")
            return {"action": action, "ready": True, "error": f"Missing service or unknown action for '{action}'"}
