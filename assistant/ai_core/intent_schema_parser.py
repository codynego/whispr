from typing import Dict, Any, Optional, List
import difflib


class IntentSchemaParser:
    """
    Validates detected intents against predefined schemas and ensures
    required entities are available before routing.
    
    ✅ Supports:
    - Multi-channel awareness (email, whatsapp, slack, etc.)
    - Dynamic fallback for unknown or partially matched intents
    - Context inheritance for missing entities
    - Alignment with LLM detector (e.g., next_run_at, workflow derivation)
    """

    def __init__(self):
        self.intent_schemas: Dict[str, Dict[str, Any]] = {
            # ---------------- EMAIL / GENERIC MESSAGE INTENTS ---------------- #
            "read_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text", "message_id", "channel"],
                "data_source": "emails",  # Dynamic override in validate
                "handler": "read_message",
            },
            "find_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text", "channel"],
                "data_source": "emails",  # Dynamic
                "handler": "query_messages",
            },
            "send_message": {  # Generic for email/chat
                "required_fields": ["receiver"],
                "optional_fields": ["subject", "body", "content", "attachments", "channel"],
                "data_source": "messages",  # Dynamic: emails/chats
                "handler": "send_message",
            },
            "reply_message": {
                "required_fields": ["message_id"],
                "optional_fields": ["body", "receiver", "subject", "channel"],
                "data_source": "messages",  # Dynamic
                "handler": "reply_message",
            },
            "summarize_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text", "channel"],
                "data_source": "emails",  # Dynamic
                "handler": "summarize_message",
            },
            "summarize_thread": {
                "required_fields": [],
                "optional_fields": ["thread_id", "sender", "timeframe", "channel"],
                "data_source": "emails",
                "handler": "summarize_thread",
            },

            # ---------------- TASKS & REMINDERS ---------------- #
            "create_task": {
                "required_fields": ["next_run_at"],  # Aligned with detector
                "optional_fields": ["context", "priority", "task_title", "due_datetime"],  # Alias support
                "data_source": "tasks",
                "handler": "create_task",
            },
            "set_reminder": {
                "required_fields": ["next_run_at"],
                "optional_fields": ["context", "priority", "task_title", "due_date", "due_time", "due_datetime"],
                "data_source": "tasks",
                "handler": "create_reminder",
            },
            "find_task": {
                "required_fields": [],
                "optional_fields": ["status", "priority", "timeframe"],
                "data_source": "tasks",
                "handler": "query_tasks",
            },

            # ---------------- CALENDAR / EVENTS ---------------- #
            "find_meeting": {
                "required_fields": [],
                "optional_fields": ["participants", "timeframe", "topic"],
                "data_source": "calendar",
                "handler": "query_meetings",
            },
            "create_event": {
                "required_fields": ["event_title", "timeframe"],
                "optional_fields": ["participants", "location", "notes"],
                "data_source": "calendar",
                "handler": "create_event",
            },

            # ---------------- INSIGHTS & GENERIC ---------------- #
            "insights": {
                "required_fields": [],
                "optional_fields": ["query_text", "timeframe", "channel"],
                "data_source": "insights",
                "handler": "generate_insights",
            },
            "summarize_any": {
                "required_fields": [],
                "optional_fields": ["context", "source_type", "channel"],
                "data_source": "any",
                "handler": "summarize_generic",
            },
            "unknown": {
                "required_fields": [],
                "optional_fields": [],
                "data_source": None,
                "handler": "unknown_intent",
            },

            # ---------------- AUTOMATIONS ---------------- #
            "automation_create": {
                "required_fields": ["trigger_type", "action_type"],  # Derived from workflow if missing
                "optional_fields": [
                    "name", "description", "next_run_at", "recurrence_pattern", "trigger_condition",
                    "action_params", "execution_mode", "context", "workflow", "__should_create_automation__",
                ],
                "data_source": "automations",
                "handler": "create_automation",
            },
            "automation_update": {
                "required_fields": ["automation_id"],
                "optional_fields": ["name", "description", "trigger_type", "action_type", "next_run_at", "recurrence_pattern", "trigger_condition", "action_params", "is_active", "workflow"],
                "data_source": "automations",
                "handler": "update_automation",
            },
            "automation_delete": {
                "required_fields": ["automation_id"],
                "optional_fields": [],
                "data_source": "automations",
                "handler": "delete_automation",
            },
            "automation_list": {
                "required_fields": [],
                "optional_fields": ["is_active", "action_type"],
                "data_source": "automations",
                "handler": "list_automations",
            },

            # ---------------- LEGACY / CHANNEL-SPECIFIC (for fallback) ---------------- #
            # Kept for close-matches, but generics preferred
            "send_email": {
                "required_fields": ["receiver"],
                "optional_fields": ["subject", "body", "attachments"],
                "data_source": "emails",
                "handler": "send_message",
            },
            "send_chat": {
                "required_fields": ["receiver"],
                "optional_fields": ["content", "attachments"],
                "data_source": "chats",
                "handler": "send_message",
            },
            "read_chat": {
                "required_fields": [],
                "optional_fields": ["sender", "timeframe", "query_text"],
                "data_source": "chats",
                "handler": "read_chat",
            },
            "find_chat": {
                "required_fields": [],
                "optional_fields": ["sender", "timeframe", "query_text"],
                "data_source": "chats",
                "handler": "query_chats",
            },
            "find_document": {
                "required_fields": [],
                "optional_fields": ["file_type", "sender", "timeframe"],
                "data_source": "files",
                "handler": "query_documents",
            },
            "find_transaction": {
                "required_fields": ["type"],
                "optional_fields": ["timeframe", "amount"],
                "data_source": "transactions",
                "handler": "query_transactions",
            },
        }

    # ---------------- VALIDATION ---------------- #
    def validate(
        self,
        detected_intent: Dict[str, Any],
        previous_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validates AI-detected intent and enriches it with missing info
        from prior context or inferred channel.
        """
        intent = detected_intent.get("intent", "unknown")
        entities = detected_intent.get("entities", {}) or {}
        confidence = detected_intent.get("confidence", 0.5)
        channel = detected_intent.get("channel")

        # 1️⃣ Infer channel if not provided
        channel = channel or self._infer_channel(intent, entities, previous_context)

        # 2️⃣ Find closest known intent (stricter cutoff)
        if intent not in self.intent_schemas:
            match = difflib.get_close_matches(intent, self.intent_schemas.keys(), n=1, cutoff=0.7)
            intent = match[0] if match else "unknown"

        schema = self.intent_schemas[intent]

        # 3️⃣ Merge entities from previous context
        if previous_context and "entities" in previous_context:
            for k, v in previous_context["entities"].items():
                entities.setdefault(k, v)

        # 4️⃣ Map common field aliases (e.g., for date compatibility)
        self._map_field_aliases(entities)

        # 5️⃣ Dynamic data_source for generic intents
        if schema["data_source"] == "messages" and channel:
            schema["data_source"] = f"{channel}s"

        # 6️⃣ Special handling for automations: Derive from workflow
        if intent.startswith("automation_") and "workflow" in entities:
            self._derive_automation_fields(entities, schema)

        # 7️⃣ Identify missing fields
        missing = [f for f in schema["required_fields"] if f not in entities]

        # 8️⃣ Bypass for flagged automations
        if intent == "automation_create" and entities.get("__should_create_automation__", False):
            missing = []

        # 9️⃣ Return appropriate response
        if missing:
            return {
                "status": "incomplete",
                "intent": intent,
                "channel": channel,
                "missing_fields": missing,
                "entities": entities,
                "message": self._generate_followup(intent, missing),
            }

        return {
            "status": "ready",
            "intent": intent,
            "channel": channel,
            "confidence": confidence,
            "entities": entities,
            "handler": schema["handler"],
            "data_source": schema["data_source"],
        }

    def _map_field_aliases(self, entities: Dict[str, Any]):
        """Map aliases like next_run_at ↔ due_datetime."""
        aliases = {
            "next_run_at": "due_datetime",
            "due_datetime": "next_run_at",  # Bidirectional
        }
        for primary, alias in aliases.items():
            if primary in entities and alias not in entities:
                entities[alias] = entities[primary]

    def _derive_automation_fields(self, entities: Dict[str, Any], schema: Dict[str, Any]):
        """Derive trigger_type/action_type from workflow JSON if missing."""
        wf = entities.get("workflow", {})
        trigger = wf.get("trigger", {})
        actions = wf.get("actions", [])
        if "trigger_type" not in entities and trigger.get("type"):
            entities["trigger_type"] = trigger["type"]
        if "action_type" not in entities and actions:
            entities["action_type"] = actions[0]["type"]  # First action

    # ---------------- CHANNEL INFERENCE ---------------- #
    def _infer_channel(
        self,
        intent: str,
        entities: Dict[str, Any],
        previous_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Heuristics for determining the communication channel
        if the AI didn’t detect one.
        """
        text_blob = f"{intent} {' '.join(entities.keys())}".lower()

        if any(k in text_blob for k in ["email", "inbox", "subject"]):
            return "email"
        if any(k in text_blob for k in ["chat", "whatsapp", "message", "text"]):
            return "whatsapp"
        if any(k in text_blob for k in ["slack", "workspace"]):
            return "slack"
        if any(k in text_blob for k in ["meeting", "calendar", "event"]):
            return "calendar"
        if any(k in text_blob for k in ["task", "reminder"]):
            return "tasks"

        if previous_context and "channel" in previous_context:
            return previous_context["channel"]

        return "all"

    # ---------------- FOLLOW-UP PROMPTS ---------------- #
    def _generate_followup(self, intent: str, missing_fields: List[str]) -> str:
        """Generates context-aware follow-up questions for missing data."""
        if not missing_fields:
            return ""

        templates = {
            "receiver": "Who should I send it to?",
            "content": "What message should I send?",
            "timeframe": "For what period?",
            "type": "Do you mean a debit or credit transaction?",
            "subject": "What was the subject?",
            "participants": "Who was in the meeting?",
            "trigger_type": "What should trigger this automation?",
            "action_type": "What action should it perform?",
            "name": "What should this automation be called?",
            "next_run_at": "When should it run next?",
            "message_id": "Which message/thread are you referring to?",
            "event_title": "What's the event about?",
            "query_text": "What specifically would you like insights on?",
            "workflow": "Can you describe the full automation workflow?",
        }

        prompts = [templates.get(f, f"Can you provide {f}?") for f in missing_fields]
        return " ".join(prompts) + " To proceed."