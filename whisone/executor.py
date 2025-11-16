from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import inspect
import json
from django.utils import timezone

# Services
from .services.gmail_service import GmailService
from .services.calendar_service import GoogleCalendarService
from .services.note_service import NoteService
from .services.reminder_service import ReminderService
from .services.todo_service import TodoService
from .knowledge_vault_manager import KnowledgeVaultManager
from .memory_integrator import MemoryIntegrator
from .memory_extractor import MemoryExtractor

User = ...  # import from settings.AUTH_USER_MODEL if needed


class Executor:
    """
    Smart Executor that:
      - Queries KnowledgeVault first
      - Decides whether to fetch external data or use memory
      - Stores new results via MemoryIntegrator
      - Minimizes unnecessary API calls
      - Executes structured tasks
    """

    FRESHNESS_MINUTES = 15
    SIMILARITY_THRESHOLD = 0.85
    FETCH_ACTIONS = {"fetch_emails", "fetch_events", "fetch_todos", "fetch_notes", "fetch_reminders"}

    def __init__(self, user: User, gmail_creds=None, calendar_creds=None):
        self.user = user

        # Initialize services
        self.note_service = NoteService(user)
        self.reminder_service = ReminderService(user)
        self.todo_service = TodoService(user)

        self.gmail_service = GmailService(**gmail_creds) if gmail_creds else None
        self.calendar_service = GoogleCalendarService(**calendar_creds) if calendar_creds else None

        # Vault & memory integration
        self.vault = KnowledgeVaultManager(user)
        self.memory_extractor = MemoryExtractor()
        self.memory_integrator = MemoryIntegrator(user, extractor=self.memory_extractor, vault_manager=self.vault)

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
    # KNOWLEDGE VAULT HELPERS
    # -------------------------
    def query_knowledge_vault(self, action: str, params: Dict[str, Any] = None):
        key_map = {
            "fetch_emails": "emails",
            "fetch_events": "events",
            "fetch_reminders": "reminders",
            "fetch_todos": "todos",
            "fetch_notes": "notes",
        }
        keyword = key_map.get(action, action)
        if params:
            filter_str = " ".join([f"{f.get('key','')}:{f.get('value','')}" for f in params.get("filters", [])])
            keyword += f" {filter_str}".strip()
        return self.vault.query(keyword=keyword, limit=1)

    def should_query_source(self, action: str, params: Dict[str, Any], vault_entries):
        if not vault_entries:
            return True

        latest = vault_entries[0]
        age = timezone.now() - latest.timestamp
        if age > timedelta(minutes=self.FRESHNESS_MINUTES):
            return True

        query_str = json.dumps(params or {})
        query_embed = self.vault.embedding_service.embed(query_str)
        memory_embed = latest.embedding
        sim = self.vault._cosine_similarity(query_embed, memory_embed)
        return sim < self.SIMILARITY_THRESHOLD

    # -------------------------
    # MAIN EXECUTION
    # -------------------------
    def execute_tasks(self, task_plan: List[Dict[str, Any]]):
        results = []

        for step in task_plan:
            action = step.get("action")
            params = step.get("params", {})

            # FETCHABLE ACTIONS
            if action in self.FETCH_ACTIONS:
                vault_entries = self.query_knowledge_vault(action, params)
                if self.should_query_source(action, params, vault_entries):
                    # Fetch external
                    result = self._execute_single_action(action, params)
                    # Store intelligently via MemoryIntegrator
                    self.memory_integrator.ingest_from_source(content=json.dumps(result), source_type=action)
                    results.append({"action": action, "result": result, "source": "external"})
                else:
                    cached = json.loads(vault_entries[0].content) if vault_entries else []
                    results.append({"action": action, "result": cached, "source": "knowledge_vault"})
                continue

            # NON-FETCH ACTIONS
            try:
                result = self._execute_single_action(action, params)
                # Optionally store memory-significant actions
                if self.memory_extractor.should_store(result):
                    self.memory_integrator.ingest_from_source(content=json.dumps(result), source_type=action)
                results.append({"action": action, "result": result})
            except Exception as e:
                results.append({"action": action, "error": str(e)})

        return results

    # -------------------------
    # SINGLE ACTION EXECUTION
    # -------------------------
    def _execute_single_action(self, action: str, params: Dict[str, Any]):
        # ------------------- NOTES -------------------
        if action == "create_note":
            note = self._safe_call(self.note_service.create_note, {"content": params.get("content")})
            return {"id": note.id, "content": note.content}
        elif action == "update_note":
            return self._safe_call(self.note_service.update_note, {"note_id": params.get("note_id"), "content": params.get("content")})
        elif action == "delete_note":
            return self._safe_call(self.note_service.delete_note, {"note_id": params.get("note_id")})
        elif action == "fetch_notes":
            return self._safe_call(self.note_service.fetch_notes, {"filters": params.get("filters", [])})

        # ------------------- REMINDERS -------------------
        elif action == "create_reminder":
            reminder = self._safe_call(self.reminder_service.create_reminder, {
                "text": params.get("title"),
                "remind_at": self._parse_datetime(params.get("datetime"))
            })
            return {"id": reminder.id, "text": reminder.text}
        elif action == "update_reminder":
            return self._safe_call(self.reminder_service.update_reminder, {
                "reminder_id": params.get("reminder_id"),
                "text": params.get("title"),
                "remind_at": self._parse_datetime(params.get("datetime"))
            })
        elif action == "delete_reminder":
            return self._safe_call(self.reminder_service.delete_reminder, {"reminder_id": params.get("reminder_id")})
        elif action == "fetch_reminders":
            return self._safe_call(self.reminder_service.fetch_reminders, {"filters": params.get("filters", [])})

        # ------------------- TODOS -------------------
        elif action == "add_todo":
            todo = self._safe_call(self.todo_service.add_todo, {"task": params.get("task")})
            return {"id": todo.id, "task": todo.task}
        elif action == "update_todo":
            return self._safe_call(self.todo_service.update_todo, {
                "todo_id": params.get("todo_id"),
                "task": params.get("task"),
                "done": params.get("done")
            })
        elif action == "delete_todo":
            return self._safe_call(self.todo_service.delete_todo, {"todo_id": params.get("todo_id")})
        elif action == "fetch_todos":
            return self._safe_call(self.todo_service.fetch_todos, {"filters": params.get("filters", [])})

        # ------------------- GMAIL -------------------
        elif action == "fetch_emails" and self.gmail_service:
            filters = params.get("filters", [])
            query = ""
            after = before = None
            unread_only = False
            max_results = params.get("max_results", 20)

            for f in filters:
                key, value = f.get("key","").lower(), f.get("value","")
                if key == "keyword": query += f" {value}"
                elif key == "from": query += f" from:{value}"
                elif key == "to": query += f" to:{value}"
                elif key == "subject": query += f" subject:{value}"
                elif key == "unread": unread_only = bool(value)
                elif key == "after": after = self._parse_datetime(value)
                elif key == "before": before = self._parse_datetime(value)

            return self._safe_call(self.gmail_service.fetch_emails, {
                "query": query.strip(),
                "after": after,
                "before": before,
                "unread_only": unread_only,
                "max_results": max_results
            })
        elif action == "mark_email_read" and self.gmail_service:
            self._safe_call(self.gmail_service.mark_as_read, {"email_id": params.get("email_id")})
            return True

        # ------------------- CALENDAR -------------------
        elif action == "fetch_events" and self.calendar_service:
            return self._safe_call(self.calendar_service.fetch_events, {
                "time_min": self._parse_datetime(params.get("time_min")),
                "time_max": self._parse_datetime(params.get("time_max")),
                "filters": params.get("filters", []),
                "max_results": params.get("max_results", 10)
            })
        elif action == "create_event" and self.calendar_service:
            return self._safe_call(self.calendar_service.create_event, {
                "summary": params.get("summary"),
                "start_time": self._parse_datetime(params.get("start_time"))
            })
        elif action == "update_event" and self.calendar_service:
            return self._safe_call(self.calendar_service.update_event, {
                "event_id": params.get("event_id"),
                "summary": params.get("summary"),
                "start_time": self._parse_datetime(params.get("start_time"))
            })
        elif action == "delete_event" and self.calendar_service:
            return self._safe_call(self.calendar_service.delete_event, {"event_id": params.get("event_id")})

        else:
            return f"Unknown action or missing service for {action}"
