from typing import Dict, Any, List

class TaskFrameBuilder:
    """
    Build task frames for the Task Planner → Executor pipeline.
    Validates parameters, finds missing fields, and structures actions
    in a consistent, machine-processable format.
    """

    def __init__(self):
        # REQUIRED fields for each action
        self.required_fields = {
            # Calendar
            "create_event": ["summary", "start_time"],
            "update_event": ["event_id"],
            "delete_event": ["event_id"],
            "fetch_events": [],

            # Notes
            "create_note": ["content"],
            "update_note": ["note_id", "content"],
            "delete_note": ["note_id"],
            "fetch_notes": [],

            # Reminders
            "create_reminder": ["text", "remind_at"],
            "update_reminder": ["reminder_id"],
            "delete_reminder": ["reminder_id"],
            "fetch_reminders": [],

            # Todos
            "create_todo": ["task"],
            "update_todo": ["todo_id"],
            "delete_todo": ["todo_id"],
            "fetch_todos": [],

            # Emails
            "mark_email_read": ["msg_id"],
            "send_email": ["to", "subject", "body"],
            "fetch_emails": []
        }

        # OPTIONAL fields for each action
        self.optional_fields = {
            # Calendar
            "create_event": ["description", "end_time", "attendees", "timezone", "service"],
            "update_event": ["summary", "description", "start_time", "end_time", "attendees", "timezone", "service"],
            "delete_event": ["service"],
            "fetch_events": ["time_min", "time_max", "max_results", "service"],

            # Notes
            "create_note": ["title", "tags"],
            "update_note": ["title", "tags"],
            "delete_note": [],
            "fetch_notes": [],

            # Reminders
            "create_reminder": ["timezone", "completed"],
            "update_reminder": ["text", "remind_at", "completed", "timezone"],
            "delete_reminder": [],
            "fetch_reminders": ["include_completed"],

            # Todos
            "create_todo": ["due_date", "priority", "done"],
            "update_todo": ["task", "due_date", "priority", "done"],
            "delete_todo": [],
            "fetch_todos": ["done"],

            # Emails
            "mark_email_read": [],
            "send_email": ["cc", "bcc"],
            "fetch_emails": ["from_email", "query", "after", "before", "unread_only", "max_results"]
        }

    # --------------------------------------------------------------
    # PUBLIC METHOD → Build Task Frame
    # --------------------------------------------------------------
    def build(self, intent: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a fully structured task frame including:
        - intent
        - action
        - parameters
        - required_fields
        - missing_fields
        - ready flag
        """
        required = self.required_fields.get(action, [])
        missing = [field for field in required if field not in parameters or parameters[field] in (None, "")]

        task_frame = {
            "intent": intent,
            "action": action,
            "parameters": parameters,
            "required_fields": required,
            "missing_fields": missing,
            "ready": len(missing) == 0
        }

        return task_frame

    # --------------------------------------------------------------
    # VALIDATION helper
    # --------------------------------------------------------------
    def validate_parameters(self, action: str, parameters: Dict[str, Any]) -> bool:
        """Return True if all required fields are present."""
        required = self.required_fields.get(action, [])
        return all(param in parameters for param in required)

    # --------------------------------------------------------------
    # POST-PROCESSING — Fill defaults for optional fields
    # --------------------------------------------------------------
    def apply_defaults(self, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Fill missing optional values with None to keep structure stable."""
        for field in self.optional_fields.get(action, []):
            parameters.setdefault(field, None)
        return parameters
