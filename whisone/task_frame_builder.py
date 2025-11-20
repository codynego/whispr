from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from whisone.natural_resolver import NaturalResolver
from whisone.services.calendar_service import GoogleCalendarService

class TaskFrameBuilder:
    """
    Build task frames for the Task Planner → Executor pipeline.
    Validates parameters, finds missing fields, resolves IDs using NaturalResolver,
    and structures actions in a consistent, machine-processable format.
    Includes debug prints to trace parameter resolution and ID lookup.
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

        self.default_timezone = "Africa/Lagos"
        self.param_mapping = {
            "create_reminder": {"datetime": "remind_at", "title": "text"},
            "update_reminder": {"datetime": "remind_at", "title": "text"},
            "create_event": {"datetime": "start_time", "title": "summary"},
            "update_event": {"datetime": "start_time", "title": "summary"}
        }

    # -------------------------------------------------------
    def build(self, intent: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        parameters = self._normalize_params(action, parameters)
        parameters = self._apply_event_defaults(action, parameters)
        parameters = self.apply_defaults(action, parameters)
        parameters = self._resolve_missing_ids(action, parameters)

        required = self.required_fields.get(action, [])
        missing = [f for f in required if f not in parameters or parameters[f] in (None, "")]
        ready = len(missing) == 0

        print(f"🔹 TaskFrameBuilder.build -> intent: {intent}, action: {action}")
        print(f"   Parameters after normalization & defaults: {parameters}")
        print(f"   Required fields: {required}")
        print(f"   Missing fields: {missing}")
        print(f"   Ready: {ready}\n")

        return {
            "intent": intent,
            "action": action,
            "parameters": parameters,
            "required_fields": required,
            "missing_fields": missing,
            "ready": ready
        }

    # -------------------------------------------------------
    def _normalize_params(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if action in self.param_mapping:
            mapping = self.param_mapping[action]
            for old_key, new_key in mapping.items():
                if old_key in parameters and new_key not in parameters:
                    parameters[new_key] = parameters.pop(old_key)
                    print(f"   🔄 Normalized param '{old_key}' -> '{new_key}'")
        return parameters

    # -------------------------------------------------------
    def _apply_event_defaults(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if action not in ("create_event", "update_event"):
            return parameters
        parameters.setdefault("timezone", self.default_timezone)
        if "start_time" in parameters and "end_time" not in parameters and parameters["start_time"]:
            try:
                dt_start = datetime.fromisoformat(parameters["start_time"])
                parameters["end_time"] = (dt_start + timedelta(hours=1)).isoformat()
                print(f"   ⏱️ Auto-generated end_time: {parameters['end_time']}")
            except Exception:
                print("   ⚠️ Failed to parse start_time for end_time default")
        return parameters

    # -------------------------------------------------------
    def apply_defaults(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        for field in self.optional_fields.get(action, []):
            parameters.setdefault(field, None)
        return parameters

    # -------------------------------------------------------
    def _resolve_missing_ids(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if not self.resolver:
            return parameters

        id_field = f"{action.split('_')[1]}_id"
        if id_field in parameters and parameters[id_field]:
            print(f"   ✅ ID already present for {id_field}: {parameters[id_field]}")
            return parameters

        query = parameters.get("text") or parameters.get("task") or parameters.get("summary") or parameters.get("title")
        if not query:
            print(f"   ⚠️ No query text found for resolving {id_field}")
            return parameters

        item_type_map = {"note": "note", "reminder": "reminder", "todo": "todo", "event": "event"}
        base_action = action.split("_")[1] if "_" in action else action
        item_type = item_type_map.get(base_action)
        if not item_type:
            print(f"   ⚠️ Unknown item type for action '{action}'")
            return parameters

        resolved = self.resolver.resolve(item_type=item_type, natural_query=query)
        if resolved and "object_id" in resolved:
            parameters[id_field] = resolved["object_id"]
            print(f"   🟢 Resolved {id_field} using NaturalResolver: {parameters[id_field]}")
        else:
            print(f"   🔴 Could not resolve {id_field} for query: '{query}'")

        return parameters
