from typing import List, Dict, Any
from datetime import datetime
import inspect

# Import your services
from .services.gmail_service import GmailService
from .services.calendar_service import GoogleCalendarService
from .services.note_service import NoteService
from .services.reminder_service import ReminderService
from .services.todo_service import TodoService
# from .whatsapp_service import WhatsAppService  # Optional


class Executor:
    def __init__(self, user, gmail_creds=None, calendar_creds=None):
        self.user = user

        # Initialize services
        self.note_service = NoteService(user)
        self.reminder_service = ReminderService(user)
        self.todo_service = TodoService(user)

        self.gmail_service = GmailService(**gmail_creds) if gmail_creds else None
        self.calendar_service = GoogleCalendarService(**calendar_creds) if calendar_creds else None
        # self.whatsapp_service = WhatsAppService(user)  # Optional

    def _safe_call(self, func, params: Dict[str, Any]):
        """
        Calls a function with only the parameters it accepts.
        Prevents TypeError from unexpected kwargs.
        """
        sig = inspect.signature(func)
        allowed_params = {
            k: v for k, v in params.items() if k in sig.parameters
        }
        return func(**allowed_params)

    def execute_task(self, task_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []

        for step in task_plan:
            action = step.get("action")
            params = step.get("params", {})

            try:
                if action == "create_note":
                    mapped_params = {"content": params.get("content", "")}
                    note = self._safe_call(self.note_service.create_note, mapped_params)
                    results.append({"action": action, "result": {"id": note.id, "content": note.content}})

                elif action == "update_note":
                    mapped_params = {
                        "note_id": params.get("note_id"),
                        "content": params.get("content", "")
                    }
                    note = self._safe_call(self.note_service.update_note, mapped_params)
                    results.append({"action": action, "result": note})

                elif action == "delete_note":
                    mapped_params = {"note_id": params.get("note_id")}
                    success = self._safe_call(self.note_service.delete_note, mapped_params)
                    results.append({"action": action, "result": success})

                elif action == "create_reminder":
                    mapped_params = {
                        "text": params.get("title", ""),
                        "remind_at": params.get("datetime")
                    }
                    reminder = self._safe_call(self.reminder_service.create_reminder, mapped_params)
                    results.append({"action": action, "result": {"id": reminder.id, "text": reminder.text}})

                elif action == "update_reminder":
                    mapped_params = {
                        "reminder_id": params.get("reminder_id"),
                        "text": params.get("title", ""),
                        "remind_at": params.get("datetime")
                    }
                    reminder = self._safe_call(self.reminder_service.update_reminder, mapped_params)
                    results.append({"action": action, "result": reminder})

                elif action == "delete_reminder":
                    mapped_params = {"reminder_id": params.get("reminder_id")}
                    success = self._safe_call(self.reminder_service.delete_reminder, mapped_params)
                    results.append({"action": action, "result": success})

                elif action == "add_todo":
                    mapped_params = {"task": params.get("task", "")}
                    todo = self._safe_call(self.todo_service.add_todo, mapped_params)
                    results.append({"action": action, "result": {"id": todo.id, "task": todo.task}})

                elif action == "update_todo":
                    mapped_params = {
                        "todo_id": params.get("todo_id"),
                        "task": params.get("task", None),
                        "done": params.get("done", None)
                    }
                    todo = self._safe_call(self.todo_service.update_todo, mapped_params)
                    results.append({"action": action, "result": todo})

                elif action == "delete_todo":
                    mapped_params = {"todo_id": params.get("todo_id")}
                    success = self._safe_call(self.todo_service.delete_todo, mapped_params)
                    results.append({"action": action, "result": success})


                elif action == "fetch_emails" and self.gmail_service:
                    emails = self._safe_call(self.gmail_service.fetch_emails, params)
                    results.append({"action": action, "result": emails})

                elif action == "mark_email_read" and self.gmail_service:
                    self._safe_call(self.gmail_service.mark_as_read, params)
                    results.append({"action": action, "result": True})
                    
                elif action == "fetch_events" and self.calendar_service:
                    events = self._safe_call(self.calendar_service.fetch_events, params)

                    results.append({"action": action, "result": events})
                elif action == "create_event" and self.calendar_service:
                    event = self._safe_call(self.calendar_service.create_event, params)
                    results.append({"action": action, "result": event})

                elif action == "update_event" and self.calendar_service:
                    event = self._safe_call(self.calendar_service.update_event, params)
                    results.append({"action": action, "result": event})

                elif action == "delete_event" and self.calendar_service:
                    success = self._safe_call(self.calendar_service.delete_event, params)
                    results.append({"action": action, "result": success})

                else:
                    results.append({"action": action, "result": "Unknown action or service not initialized"})

            except Exception as e:
                results.append({"action": action, "error": str(e)})

        return results
