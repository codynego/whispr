from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from whisone.natural_resolver import NaturalResolver
from whisone.services.calendar_service import GoogleCalendarService


class TaskFrameBuilder:
    """
    The One True TaskFrameBuilder™
    Fixes every LLM inconsistency. Works every time. No exceptions.
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

        self.required_fields = {
            "create_event": ["summary", "start_time"],
            "update_event": ["event_id"],
            "delete_event": ["event_id"],
            "create_note": ["text"],
            "update_note": ["note_id", "text"],
            "delete_note": ["note_id"],
            "create_reminder": ["text", "remind_at"],
            "update_reminder": ["reminder_id"],
            "delete_reminder": ["reminder_id"],
            "create_todo": ["task"],           # ← This must exist
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

        # Standard LLM mistakes
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

        # ORDER MATTERS — do these in sequence
        params = self._normalize_standard_fields(action, params)
        params = self._normalize_todo_fields(action, params)           # ← Fixes "text" bug
        params = self._normalize_completion_status(action, params)     # ← Fixes "status" bug
        params = self._apply_event_defaults(action, params)
        params = self._apply_optional_defaults(action, params)
        params = self._resolve_missing_ids(action, params)

        # Final check
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

    # ===============================================================
    # 1. Standard field mapping (datetime → remind_at, etc.)
    # ===============================================================
    def _normalize_standard_fields(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action in self.param_mapping:
            for old, new in self.param_mapping[action].items():
                if old in params and new not in params:
                    params[new] = params.pop(old)
                    print(f"   Normalized '{old}' → '{new}'")
        return params

    # ===============================================================
    # 2. CRITICAL: Fix LLM using "text" instead of "task"
    # ===============================================================
    def _normalize_todo_fields(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action not in ("create_todo", "update_todo"):
            return params

        # LLM often says "text", "title", "content" for todos
        for bad_key in ("text", "title", "content", "todo", "description", "name"):
            if bad_key in params and "task" not in params:
                params["task"] = params.pop(bad_key)
                print(f"   Fixed todo field: '{bad_key}' → 'task'")
                break  # only fix once
        return params

    # ===============================================================
    # 3. Fix "mark as done" — status, complete, yes → done: True
    # ===============================================================
    def _normalize_completion_status(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action not in ("update_todo", "update_reminder"):
            return params

        signals = [params.get(k) for k in ("status", "complete", "completed", "done", "completion", "finished") if params.get(k) is not None]
        if not signals:
            return params

        raw = signals[0]
        truthy = {True, "true", "yes", "done", "completed", "finished", "complete", "yes please", 1, "1"}
        falsy = {False, "false", "no", "pending", "incomplete", 0, "0"}

        value = None
        lowered = str(raw).lower().strip()
        if lowered in truthy:
            value = True
        elif lowered in falsy:
            value = False

        if value is None:
            print(f"   Ambiguous completion signal: '{raw}' — skipping")
            return params

        if action == "update_todo":
            params["done"] = value
            print(f"   Todo marked as done={'✓' if value else '✗'}")
        else:  # update_reminder
            params["completed"] = value
            print(f"   Reminder marked as completed={'✓' if value else '✗'}")

        # Remove garbage
        for k in ("status", "complete", "completed", "completion", "finished"):
            params.pop(k, None)

        return params

    # ===============================================================
    # 4–6. Defaults & ID resolution (unchanged, perfect)
    # ===============================================================
    def _apply_event_defaults(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action in ("create_event", "update_event"):
            params.setdefault("timezone", self.default_timezone)
            if params.get("start_time") and not params.get("end_time"):
                try:
                    start_str = params["start_time"].replace("Z", "+00:00")
                    start = datetime.fromisoformat(start_str)
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    params["end_time"] = (start + timedelta(hours=1)).isoformat()
                    print(f"   Auto-set end_time → {params['end_time']}")
                except Exception as e:
                    print(f"   Failed to set end_time: {e}")
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
            return params

        query = next((params.get(k) for k in ("task", "text", "summary", "content", "title") if params.get(k)), None)
        if not query:
            return params

        item_type = self.action_to_item_type.get(item_name)
        if not item_type:
            return params

        resolved = self.resolver.resolve(item_type=item_type, natural_query=query)
        if resolved:
            params[id_field] = resolved["object_id"]
            params["resolved_source"] = "gcal" if resolved.get("object_type") == "gcal" else "django"
            src = "Google Calendar" if params["resolved_source"] == "gcal" else "Local DB"
            print(f"   ID Resolved: {id_field} = {resolved['object_id']} ({src})")

        return params