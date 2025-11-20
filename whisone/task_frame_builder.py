from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from whisone.natural_resolver import NaturalResolver
from whisone.services.calendar_service import GoogleCalendarService


class TaskFrameBuilder:
    """
    Enhanced TaskFrameBuilder that works seamlessly with the new NaturalResolver.
    Correctly resolves IDs for both Django objects (int PK) and Google Calendar events (string ID).
    Adds metadata like `resolved_source` for proper executor routing.
    """

    def __init__(
        self,
        user=None,
        resolver: Optional[NaturalResolver] = None,
        calendar_service: Optional[GoogleCalendarService] = None,
    ):
        self.user = user
        self.resolver = resolver
        self.calendar_service = calendar_service
        self.default_timezone = "Africa/Lagos"

        # ==================== ACTION CONFIG ====================
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
            "fetch_emails": [],
        }

        self.optional_fields = {
            "create_event": ["description", "end_time", "attendees", "timezone", "service"],
            "update_event": ["summary", "description", "start_time", "end_time", "attendees", "timezone", "service"],
            "delete_event": ["service"],
            "fetch_events": ["time_min", "time_max", "max_results", "service"],
            "create_note": ["title", "tags"],
            "update_note": ["title", "tags"],
            "create_reminder": ["timezone", "completed"],
            "update_reminder": ["text", "remind_at", "completed", "timezone"],
            "create_todo": ["due_date", "priority", "done"],
            "update_todo": ["task", "due_date", "priority", "done"],
            "send_email": ["cc", "bcc"],
            "fetch_emails": ["from_email", "query", "after", "before", "unread_only", "max_results"],
        }

        # Normalize common LLM outputs → correct field names
        self.param_mapping = {
            "create_reminder": {"datetime": "remind_at", "title": "text"},
            "update_reminder": {"datetime": "remind_at", "title": "text"},
            "create_event": {"datetime": "start_time", "title": "summary"},
            "update_event": {"datetime": "start_time", "title": "summary"},
        }

        # Map action → item type for NaturalResolver
        self.action_to_item_type = {
            "note": "note",
            "reminder": "reminder",
            "todo": "todo",
            "event": "event",
        }

    # =========================================================
    def build(self, intent: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        parameters = self._normalize_params(action, parameters.copy())
        parameters = self._apply_event_defaults(action, parameters)
        parameters = self._apply_optional_defaults(action, parameters)
        parameters = self._resolve_missing_ids(action, parameters)

        required = self.required_fields.get(action, [])
        missing = [f for f in required if not parameters.get(f)]
        ready = len(missing) == 0

        print(f"\nTaskFrameBuilder → {intent} | {action}")
        print(f"   Parameters: {parameters}")
        print(f"   Missing: {missing} → Ready: {ready}")

        frame = {
            "intent": intent,
            "action": action,
            "parameters": parameters,
            "required_fields": required,
            "missing_fields": missing,
            "ready": ready,
        }

        # Add resolved source for executor routing
        if "resolved_source" in parameters:
            frame["resolved_source"] = parameters["resolved_source"]

        return frame

    # =========================================================
    def _normalize_params(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action in self.param_mapping:
            mapping = self.param_mapping[action]
            for old, new in mapping.items():
                if old in params and new not in params:
                    params[new] = params.pop(old)
                    print(f"   Normalized '{old}' → '{new}'")
        return params

    # =========================================================
    def _apply_event_defaults(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action in ("create_event", "update_event"):
            params.setdefault("timezone", self.default_timezone)

            if params.get("start_time") and not params.get("end_time"):
                try:
                    start = datetime.fromisoformat(params["start_time"].replace("Z", "+00:00"))
                    end = start + timedelta(hours=1)
                    params["end_time"] = end.isoformat()
                    print(f"   Auto-set end_time → {params['end_time']}")
                except Exception as e:
                    print(f"   Failed to parse start_time for end_time: {e}")
        return params

    # =========================================================
    def _apply_optional_defaults(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        for field in self.optional_fields.get(action, []):
            params.setdefault(field, None)
        return params

    # =========================================================
    def _resolve_missing_ids(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.resolver:
            print("   No resolver available")
            return params

        # Determine which ID field we need
        if not action.startswith(("update_", "delete_")):
            return params

        item_name = action.split("_")[1]  # "event", "note", "reminder", "todo"
        id_field = f"{item_name}_id"

        if params.get(id_field):
            print(f"   ID already set: {id_field} = {params[id_field]}")
            return params

        # Build natural language query from available text fields
        query_sources = ["summary", "text", "task", "content", "title", "description"]
        query = next((params.get(k) for k in query_sources if params.get(k)), None)

        if not query:
            print(f"   No text query available to resolve {id_field}")
            return params

        item_type = self.action_to_item_type.get(item_name)
        if not item_type:
            print(f"   Unknown item type for action: {action}")
            return params

        print(f"   Resolving '{query}' → {item_type}...")

        resolved = self.resolver.resolve(item_type=item_type, natural_query=query)

        if not resolved:
            print(f"   Failed to resolve any {item_type} for: '{query}'")
            return params

        resolved_id = resolved["object_id"]
        object_type = resolved.get("object_type", "django")
        confidence = resolved.get("confidence", 0.0)
        source = resolved.get("source", "unknown")

        params[id_field] = resolved_id
        params["resolved_source"] = "gcal" if object_type == "gcal" else "django"

        src_label = "Google Calendar" if object_type == "gcal" else "Local DB"
        print(f"   Resolved {id_field} = {resolved_id}")
        print(f"       → Source: {src_label} | Method: {source} | Confidence: {confidence:.3f}")
        print(f"       → Matched: \"{resolved.get('matched_text', '')[:80]}...\"")

        return params