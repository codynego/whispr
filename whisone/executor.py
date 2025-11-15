from typing import List, Dict, Any
from datetime import datetime

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

        # Only initialize if credentials are provided
        self.gmail_service = GmailService(**gmail_creds) if gmail_creds else None
        self.calendar_service = GoogleCalendarService(**calendar_creds) if calendar_creds else None
        # self.whatsapp_service = WhatsAppService(user)  # Optional

    def execute_task(self, task_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        task_plan: List of actions, e.g.
        [
            {"action": "fetch_emails", "params": {"query": "interview", "unread_only": True}},
            {"action": "create_event", "params": {"summary": "Interview", "start_time": datetime_obj, "end_time": datetime_obj}},
            {"action": "create_reminder", "params": {"text": "Interview tomorrow", "remind_at": datetime_obj}}
        ]
        """
        results = []

        for step in task_plan:
            action = step.get("action")
            params = step.get("params", {})

            try:
                if action == "create_note":
                    note = self.note_service.create_note(params["content"])
                    results.append({"action": action, "result": {"id": note.id, "content": note.content}})

                elif action == "update_note":
                    note = self.note_service.update_note(params["note_id"], params["content"])
                    results.append({"action": action, "result": note})

                elif action == "delete_note":
                    success = self.note_service.delete_note(params["note_id"])
                    results.append({"action": action, "result": success})

                elif action == "create_reminder":
                    reminder = self.reminder_service.create_reminder(params["text"], params["remind_at"])
                    results.append({"action": action, "result": {"id": reminder.id, "text": reminder.text}})

                elif action == "update_reminder":
                    reminder = self.reminder_service.update_reminder(params["reminder_id"], params.get("text"), params.get("remind_at"))
                    results.append({"action": action, "result": reminder})

                elif action == "delete_reminder":
                    success = self.reminder_service.delete_reminder(params["reminder_id"])
                    results.append({"action": action, "result": success})

                elif action == "add_todo":
                    todo = self.todo_service.add_todo(params["task"])
                    results.append({"action": action, "result": {"id": todo.id, "task": todo.task}})

                elif action == "update_todo":
                    todo = self.todo_service.update_todo(params["todo_id"], params.get("task"), params.get("done"))
                    results.append({"action": action, "result": todo})

                elif action == "delete_todo":
                    success = self.todo_service.delete_todo(params["todo_id"])
                    results.append({"action": action, "result": success})

                elif action == "fetch_emails":
                    if self.gmail_service:
                        emails = self.gmail_service.fetch_emails(**params)
                        results.append({"action": action, "result": emails})

                elif action == "mark_email_read":
                    if self.gmail_service:
                        self.gmail_service.mark_as_read(params["msg_id"])
                        results.append({"action": action, "result": True})

                elif action == "create_event":
                    if self.calendar_service:
                        event = self.calendar_service.create_event(**params)
                        results.append({"action": action, "result": event})

                elif action == "update_event":
                    if self.calendar_service:
                        event = self.calendar_service.update_event(**params)
                        results.append({"action": action, "result": event})

                elif action == "delete_event":
                    if self.calendar_service:
                        success = self.calendar_service.delete_event(params["event_id"])
                        results.append({"action": action, "result": success})

                # Add more actions here (WhatsApp, other services)
                else:
                    results.append({"action": action, "result": "Unknown action"})

            except Exception as e:
                results.append({"action": action, "error": str(e)})

        return results
