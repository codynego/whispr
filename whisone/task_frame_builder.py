from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from natural_resolver import NaturalResolver
from calendar_service import GoogleCalendarService

class TaskFrameBuilder:
    """
    Build task frames for the Task Planner → Executor pipeline.
    Validates parameters, finds missing fields, resolves IDs using NaturalResolver,
    and structures actions in a consistent, machine-processable format.
    """


    def __init__(self, user=None, resolver: Optional[NaturalResolver] = None, calendar_service: Optional[GoogleCalendarService] = None):
        self.user = user
        self.resolver = resolver
        self.calendar_service = calendar_service

        # REQUIRED fields for each action
        self.required_fields = {
            "create_event": ["summary", "start_time"],
            "update_event": ["event_id"],
            "delete_event": ["event_id"],
            "fetch_events": [],
            "create_note": ["content"],
            "update_note": ["note_id", "content"],
            "delete_note": ["note_id"],
            "fetch_notes": [],
            "create_reminder": ["text", "remind_at"],
            "update_reminder": ["reminder_id"],
            "delete_reminder": ["reminder_id"],
            "fetch_reminders": [],
            "create_todo": ["task"],
            "update_todo": ["todo_id"],
            "delete_todo": ["todo_id"],
            "fetch_todos": [],
            "mark_email_read": ["msg_id"],
            "send_email": ["to", "subject", "body"],
            "fetch_emails": []
        }

        # OPTIONAL fields
        self.optional_fields = {
            "create_event": ["description", "end_time", "attendees", "timezone", "service"],
            "update_event": ["summary", "description", "start_time", "end_time", "attendees", "timezone", "service"],
            "delete_event": ["service"],
            "fetch_events": ["time_min", "time_max", "max_results", "service"],
            "create_note": ["title", "tags"],
            "update_note": ["title", "tags"],
            "delete_note": [],
            "fetch_notes": [],
            "create_reminder": ["timezone", "completed"],
            "update_reminder": ["text", "remind_at", "completed", "timezone"],
            "delete_reminder": [],
            "fetch_reminders": ["include_completed"],
            "create_todo": ["due_date", "priority", "done"],
            "update_todo": ["task", "due_date", "priority", "done"],
            "delete_todo": [],
            "fetch_todos": ["done"],
            "mark_email_read": [],
            "send_email": ["cc", "bcc"],
            "fetch_emails": ["from_email", "query", "after", "before", "unread_only", "max_results"]
        }

        # Default timezone
        self.default_timezone = "Africa/Lagos"

        # Param mapping from planner → executor
        self.param_mapping = {
            "create_reminder": {"datetime": "remind_at", "title": "text"},
            "update_reminder": {"datetime": "remind_at", "title": "text"},
            "create_event": {"datetime": "start_time", "title": "summary"},
            "update_event": {"datetime": "start_time", "title": "summary"}
        }

    # -------------------------------------------------------
    def build(self, intent: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a task frame with:
        - required fields
        - optional fields
        - resolved IDs (via NaturalResolver if missing)
        - ready flag
        """
        parameters = self._normalize_params(action, parameters)
        parameters = self._apply_event_defaults(action, parameters)
        parameters = self.apply_defaults(action, parameters)

        # Attempt to resolve missing ID fields
        parameters = self._resolve_missing_ids(action, parameters)

        required = self.required_fields.get(action, [])
        missing = [f for f in required if f not in parameters or parameters[f] in (None, "")]
        return {
            "intent": intent,
            "action": action,
            "parameters": parameters,
            "required_fields": required,
            "missing_fields": missing,
            "ready": len(missing) == 0
        }

    # -------------------------------------------------------
    def _normalize_params(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Map planner param names to executor param names"""
        if action in self.param_mapping:
            mapping = self.param_mapping[action]
            for old_key, new_key in mapping.items():
                if old_key in parameters and new_key not in parameters:
                    parameters[new_key] = parameters.pop(old_key)
        return parameters

    # -------------------------------------------------------
    def _apply_event_defaults(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default timezone and auto-generate end_time if missing"""
        if action not in ("create_event", "update_event"):
            return parameters

        parameters.setdefault("timezone", self.default_timezone)

        if "start_time" in parameters and "end_time" not in parameters and parameters["start_time"]:
            try:
                dt_start = datetime.fromisoformat(parameters["start_time"])
                parameters["end_time"] = (dt_start + timedelta(hours=1)).isoformat()
            except Exception:
                pass
        return parameters

    # -------------------------------------------------------
    def apply_defaults(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Add optional fields with None defaults"""
        for field in self.optional_fields.get(action, []):
            parameters.setdefault(field, None)
        return parameters

    # -------------------------------------------------------
    def _resolve_missing_ids(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Use NaturalResolver to auto-fill missing IDs for update/delete actions"""
        if not self.resolver:
            return parameters

        id_field = f"{action.split('_')[1]}_id"  # e.g., "note_id", "reminder_id", "todo_id", "event_id"
        if id_field in parameters and parameters[id_field]:
            return parameters  # already present

        # Determine natural query from available text fields
        query = parameters.get("text") or parameters.get("task") or parameters.get("summary") or parameters.get("title")
        if not query:
            return parameters

        # Determine item_type for resolver
        item_type_map = {
            "note": "note",
            "reminder": "reminder",
            "todo": "todo",
            "event": "event"
        }
        base_action = action.split("_")[1] if "_" in action else action
        item_type = item_type_map.get(base_action)
        if not item_type:
            return parameters

        # Resolve ID
        resolved = self.resolver.resolve(item_type=item_type, natural_query=query)
        if resolved and "object_id" in resolved:
            parameters[id_field] = resolved["object_id"]

        return parameters

