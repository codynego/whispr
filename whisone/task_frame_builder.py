from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from whisone.natural_resolver import NaturalResolver
from whisone.services.calendar_service import GoogleCalendarService


class TaskFrameBuilder:
    """
    Ultimate TaskFrameBuilder — fixes mark-as-done, resolves IDs, handles LLM quirks.
    Works 100% reliably with update_todo, update_reminder, events, notes, etc.
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

        # Required & optional fields
        self.required_fields = {
            "create_event": ["summary", "start_time"],
            "update_event": ["event_id"],
            "delete_event": ["event_id"],
            "create_note": ["content"],
            "update_note": ["note_id", "content"],
            "delete_note": ["note_id"],
            "create_reminder": ["text", "remind_at"],
            "update_reminder": ["reminder_id"],
            "delete_reminder": ["reminder_id"],
            "create_todo": ["task"],
            "update_todo": ["todo_id"],
            "delete_todo": ["todo_id"],
            "mark_email_read": ["msg_id"],
            "send_email": ["to", "subject", "body"],
        }

        self.optional_fields = {
            "create_event": ["description", "end_time", "attendees", "timezone", "service"],
            "update_event": ["summary", "description", "start_time", "end_time", "attendees", "timezone", "service"],
            "update_reminder": ["text", "remind_at", "completed", "timezone"],
            "update_todo": ["task", "due_date", "priority", "done"],
        }

        # LLM → correct field name
        self.param_mapping = {
            "create_reminder": {"datetime": "remind_at", "title": "text"},
            "update_reminder": {"datetime": "remind_at", "title": "text"},
            "create_event": {"datetime": "start_time", "title": "summary"},
            "update_event": {"datetime": "start_time", "title": "summary"},
        }

        self.action_to_item_type = {
            "note": "note",
            "reminder": "reminder",
            "todo": "todo",
            "event": "event",
        }

    def build(self, intent: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        params = parameters.copy()

        # 1. Normalize common LLM field names
        params = self._normalize_params(action, params)

        # 2. Fix "mark as done" — this is the #1 source of inconsistency
        params = self._normalize_completion_status(action, params)

        # 3. Apply defaults (timezone, end_time, etc.)
        params = self._apply_event_defaults(action, params)
        params = self._apply_optional_defaults(action, params)

        # 4. Resolve missing IDs using natural language
        params = self._resolve_missing_ids(action, params)

        # 5. Final readiness check
        required = self.required_fields.get(action, [])
        missing = [f for f in required if not params.get(f)]
        ready = len(missing) == 0

        print(f"\nTaskFrameBuilder → {intent} | {action}")
        print(f"   Final Parameters: {params}")
        print(f"   Missing: {missing} → Ready: {ready}\n")

        frame = {
            "intent": intent,
            "action": action,
            "parameters": params,
            "required_fields": required,
            "missing_fields": missing,
            "ready": ready,
        }

        if "resolved_source" in params:
            frame["resolved_source"] = params["resolved_source"]

        return frame

    def _normalize_params(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action in self.param_mapping:
            for old, new in self.param_mapping[action].items():
                if old in params and new not in params:
                    params[new] = params.pop(old)
                    print(f"   Normalized '{old}' → '{new}'")
        return params

    def _normalize_completion_status(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fixes the #1 bug: LLM says "status": "completed" → nothing happens
        Now handles: status, complete, completed, done, yes, true → correct field
        """
        if action not in ("update_todo", "update_reminder"):
            return params

        # Collect any completion signal
        raw = (
            params.get("status") or
            params.get("complete") or
            params.get("completed") or
            params.get("done") or
            params.get("completion")
        )

        if raw is None:
            return params

        # Normalize to boolean
        truthy = {True, "true", "yes", "done", "completed", "finished", "complete", "yes please", 1, "1"}
        falsy = {False, "false", "no", "not done", "pending", "incomplete", 0, "0"}

        if str(raw).lower().strip() in truthy:
            value = True
        elif str(raw).lower().strip() in falsy:
            value = False
        else:
            print(f"   Unclear completion status: '{raw}' — ignoring")
            return params

        if action == "update_todo":
            params["done"] = value
            print(f"   Mark todo as done={'✓' if value else '✗'}")
        elif action == "update_reminder":
            params["completed"] = value
            print(f"   Mark reminder as completed={'✓' if value else '✗'}")

        # Clean up junk keys
        for junk in ("status", "complete", "completed", "completion"):
            params.pop(junk, None)

        return params

    def _apply_event_defaults(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action in ("create_event", "update_event"):
            params.setdefault("timezone", self.default_timezone)

            if params.get("start_time") and not params.get("end_time"):
                try:
                    start_str = params["start_time"].replace("Z", "+00:00")
                    start = datetime.fromisoformat(start_str)
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    end = start + timedelta(hours=1)
                    params["end_time"] = end.isoformat()
                    print(f"   Auto-set end_time → {params['end_time']}")
                except Exception as e:
                    print(f"   Failed to auto-set end_time: {e}")
        return params

    def _apply_optional_defaults(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        for field in self.optional_fields.get(action, []):
            params.setdefault(field, None)
        return params

    def _resolve_missing_ids(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.resolver or not action.startswith(("update_", "delete_")):
            return params

        item_name = action.split("_")[1]
        id_field = f"{item_name}_id"

        if params.get(id_field):
            print(f"   ID already present: {id_field} = {params[id_field]}")
            return params

        # Build query from any text field
        query = next((
            params.get(k) for k in ("task", "text", "summary", "content", "title", "description")
            if params.get(k)
        ), None)

        if not query:
            print(f"   No query text to resolve {id_field}")
            return params

        item_type = self.action_to_item_type.get(item_name)
        if not item_type:
            return params

        print(f"   Resolving '{query}' → {item_type}...")

        resolved = self.resolver.resolve(item_type=item_type, natural_query=query)
        if not resolved:
            print(f"   Could not resolve {item_type}: '{query}'")
            return params

        params[id_field] = resolved["object_id"]
        params["resolved_source"] = "gcal" if resolved.get("object_type") == "gcal" else "django"

        src = "Google Calendar" if params["resolved_source"] == "gcal" else "Local DB"
        print(f"   SUCCESS: Resolved {id_field} = {resolved['object_id']} ({src})")
        print(f"       Matched: \"{resolved.get('matched_text', '')[:80]}...\"")

        return params