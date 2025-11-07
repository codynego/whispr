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
    """

    def __init__(self):
        self.intent_schemas: Dict[str, Dict[str, Any]] = {
            # ---------------- EMAIL INTENTS ---------------- #
            "read_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],
                "data_source": "emails",
                "handler": "read_message",
            },
            "find_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],
                "data_source": "emails",
                "handler": "query_messages",
            },
            "send_email": {
                "required_fields": ["receiver"],
                "optional_fields": ["subject", "body", "attachments"],
                "data_source": "emails",
                "handler": "send_message",
            },
            "summarize_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],
                "data_source": "emails",
                "handler": "summarize_message",
            },
            "summarize_thread": {
                "required_fields": [],
                "optional_fields": ["thread_id", "sender", "timeframe"],
                "data_source": "emails",
                "handler": "summarize_thread",
            },

            # ---------------- CHAT / WHATSAPP INTENTS ---------------- #
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

            # ---------------- TASKS & REMINDERS ---------------- #
            "create_task": {
                "required_fields": ["due_datetime"],
                "optional_fields": ["context", "priority", "task_title"],
                "data_source": "tasks",
                "handler": "create_task",
            },
            "set_reminder": {
                "required_fields": ["due_datetime"],
                "optional_fields": ["context", "priority", "task_title", "due_date", "due_time"],
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

            # ---------------- FILES / DOCUMENTS ---------------- #
            "find_document": {
                "required_fields": [],
                "optional_fields": ["file_type", "sender", "timeframe"],
                "data_source": "files",
                "handler": "query_documents",
            },

            # ---------------- TRANSACTIONS ---------------- #
            "find_transaction": {
                "required_fields": ["type"],
                "optional_fields": ["timeframe", "amount"],
                "data_source": "transactions",
                "handler": "query_transactions",
            },

            # ---------------- GENERIC / META ---------------- #
            "summarize_any": {
                "required_fields": [],
                "optional_fields": ["context", "source_type"],
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
                "required_fields": ["trigger_type", "action_type"],
                "optional_fields": [
                    "name", "description", "next_run_at", "recurrence_pattern", "trigger_condition",
                    "action_params", "execution_mode", "context",
                ],
                "data_source": "automations",
                "handler": "create_automation",
            },
            "automation_update": {
                "required_fields": ["automation_id"],
                "optional_fields": ["name", "description", "trigger_type", "action_type", "next_run_at", "recurrence_pattern", "trigger_condition", "action_params", "is_active"],
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

        # 2️⃣ Find closest known intent
        if intent not in self.intent_schemas:
            match = difflib.get_close_matches(intent, self.intent_schemas.keys(), n=1, cutoff=0.6)
            intent = match[0] if match else "unknown"

        schema = self.intent_schemas[intent]

        # 3️⃣ Merge entities from previous context
        if previous_context and "entities" in previous_context:
            for k, v in previous_context["entities"].items():
                entities.setdefault(k, v)

        # 4️⃣ Identify missing fields
        missing = [f for f in schema["required_fields"] if f not in entities]

        # 5️⃣ Return appropriate response
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
        if any(k in text_blob for k in ["meeting", "calendar"]):
            return "calendar"

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
        }

        prompts = [templates.get(f, f"Can you provide {f}?") for f in missing_fields]
        return " ".join(prompts)