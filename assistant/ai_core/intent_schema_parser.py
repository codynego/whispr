from typing import Dict, Any, Optional
import difflib

class IntentSchemaParser:
    """
    Validates detected intents against predefined schemas and ensures
    all required entities are available before routing.
    Supports multi-channel awareness (email, whatsapp, slack, etc.)
    and dynamic fallback for unknown intents.
    """

    def __init__(self):
        # 🎯 Base intent schema definitions
        self.intent_schemas = {
            # ---------------- EMAIL INTENTS ---------------- #
            "read_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],
                "data_source": "emails",
                "handler": "read_message"
            },
            "find_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],
                "data_source": "emails",
                "handler": "query_messages"
            },
            "send_email": {
                "required_fields": ["receiver"],
                "optional_fields": ["subject", "body", "attachments"],
                "data_source": "emails",
                "handler": "send_message"
            },
            "summarize_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],
                "data_source": "emails",
                "handler": "summarize_message"
            },
            "summarize_thread": {
                "required_fields": [],
                "optional_fields": ["thread_id", "sender", "timeframe"],
                "data_source": "emails",
                "handler": "summarize_thread"
            },

            # ---------------- CHAT / WHATSAPP INTENTS ---------------- #
            "send_chat": {
                "required_fields": ["receiver"],
                "optional_fields": ["content", "attachments"],
                "data_source": "chats",
                "handler": "send_message"
            },
            "read_chat": {
                "required_fields": [],
                "optional_fields": ["sender", "timeframe", "query_text"],
                "data_source": "chats",
                "handler": "read_chat"
            },
            "find_chat": {
                "required_fields": [],
                "optional_fields": ["sender", "timeframe", "query_text"],
                "data_source": "chats",
                "handler": "query_chats"
            },

            # ---------------- TASKS & REMINDERS ---------------- #
            "create_task": {
                "required_fields": ["due_datetime"],
                "optional_fields": ["due_datetime", "context", "priority"],
                "data_source": "tasks",
                "handler": "create_task"
            },
            "set_reminder": {
                "required_fields": ["due_datetime"],
                "optional_fields": ["context", "priority", "task_title", "due_date", "due_time"],
                "data_source": "tasks",
                "handler": "create_reminder"
            },
            "find_task": {
                "required_fields": [],
                "optional_fields": ["status", "priority", "timeframe"],
                "data_source": "tasks",
                "handler": "query_tasks"
            },

            # ---------------- CALENDAR / EVENTS ---------------- #
            "find_meeting": {
                "required_fields": [],
                "optional_fields": ["participants", "timeframe", "topic"],
                "data_source": "calendar",
                "handler": "query_meetings"
            },
            "create_event": {
                "required_fields": ["event_title", "timeframe"],
                "optional_fields": ["participants", "location", "notes"],
                "data_source": "calendar",
                "handler": "create_event"
            },

            # ---------------- FILES / DOCUMENTS ---------------- #
            "find_document": {
                "required_fields": [],
                "optional_fields": ["file_type", "sender", "timeframe"],
                "data_source": "files",
                "handler": "query_documents"
            },

            # ---------------- TRANSACTIONS ---------------- #
            "find_transaction": {
                "required_fields": ["type"],
                "optional_fields": ["timeframe", "amount"],
                "data_source": "transactions",
                "handler": "query_transactions"
            },

            # ---------------- GENERAL / META ---------------- #
            "summarize_any": {
                "required_fields": [],
                "optional_fields": ["context", "source_type"],
                "data_source": "any",
                "handler": "summarize_generic"
            },
            "unknown": {
                "required_fields": [],
                "optional_fields": [],
                "data_source": None,
                "handler": "unknown_intent"
            },
        }

    def validate(
        self,
        detected_intent: Dict[str, Any],
        previous_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validates AI-detected intent and fills missing data from previous context.
        Automatically infers channel and fills missing entities.
        """
        intent = detected_intent.get("intent", "unknown")
        entities = detected_intent.get("entities", {}) or {}
        confidence = detected_intent.get("confidence", 0.5)
        channel = detected_intent.get("channel")


        # 1️⃣ Try to auto-infer channel based on intent name or context
        if not channel:
            channel = self._infer_channel(intent, entities, previous_context)

        # 2️⃣ Map to known schema (fallback to closest match)
        if intent not in self.intent_schemas:
            possible_match = difflib.get_close_matches(intent, self.intent_schemas.keys(), n=1, cutoff=0.6)
            if possible_match:
                intent = possible_match[0]
            else:
                return {
                    "status": "unknown_intent",
                    "intent": intent,
                    "confidence": confidence,
                    "message": f"Sorry, I’m not sure how to handle '{intent}'."
                }

        schema = self.intent_schemas[intent]

        # 3️⃣ Fill missing entities from context (if available)
        if previous_context:
            last_entities = previous_context.get("entities", {})
            for k, v in last_entities.items():
                if k not in entities:
                    entities[k] = v

        # 4️⃣ Skip asking unnecessary follow-ups for intents with no required fields
        if not schema["required_fields"]:
            return {
                "status": "ready",
                "intent": intent,
                "channel": channel,
                "confidence": confidence,
                "entities": entities,
                "handler": schema["handler"],
                "data_source": schema["data_source"]
            }

        # 5️⃣ Only check required fields if they exist
        missing_fields = [f for f in schema["required_fields"] if f not in entities]

        if missing_fields:
            return {
                "status": "incomplete",
                "intent": intent,
                "channel": channel,
                "missing_fields": missing_fields,
                "entities": entities,
                "message": self.generate_followup(intent, missing_fields)
            }

        # 6️⃣ Return structured, validated command
        return {
            "status": "ready",
            "intent": intent,
            "channel": channel,
            "confidence": confidence,
            "entities": entities,
            "handler": schema["handler"],
            "data_source": schema["data_source"]
        }


    # 🧠 Infer channel when user didn’t specify one
    def _infer_channel(
        self,
        intent: str,
        entities: Dict[str, Any],
        previous_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Heuristic-based channel inference:
        - Check for channel-specific keywords in the intent or entities
        - Fallback to last known channel in previous context
        - Otherwise mark as 'all'
        """
        text_data = f"{intent} {' '.join(entities.keys())}".lower()

        if any(word in text_data for word in ["email", "inbox", "subject"]):
            return "email"
        elif any(word in text_data for word in ["chat", "whatsapp", "message", "text"]):
            return "whatsapp"
        elif any(word in text_data for word in ["meeting", "calendar"]):
            return "calendar"

        if previous_context and "channel" in previous_context:
            return previous_context["channel"]

        return "all"

    # 🗣 Generate follow-up questions when missing required entities
    def generate_followup(self, intent: str, missing_fields: list[str]) -> str:
        if not missing_fields:
            return ""

        questions = {
            "receiver": "Who should I send it to?",
            "content": "What message should I send?",
            "timeframe": "For what period?",
            "type": "Do you mean a debit or credit transaction?",
            "subject": "What was the subject?",
            "participants": "Who was in the meeting?",
        }

        prompts = [questions.get(f, f"Can you provide {f}?") for f in missing_fields]
        return " ".join(prompts)
