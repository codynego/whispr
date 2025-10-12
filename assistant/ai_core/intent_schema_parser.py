from typing import Dict, Any, Optional
import difflib

class IntentSchemaParser:
    """
    Validates detected intents against predefined schemas and ensures
    all required entities are available before routing.
    Supports dynamic fallback for AI-detected (Gemini) intents.
    """

    def __init__(self):
        self.intent_schemas = {
            "find_email": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject"],
                "data_source": "emails",
                "handler": "query_emails"
            },
            "find_transaction": {
                "required_fields": ["type"],
                "optional_fields": ["timeframe", "amount"],
                "data_source": "transactions",
                "handler": "query_transactions"
            },
            "find_task": {
                "required_fields": [],
                "optional_fields": ["status", "priority", "timeframe"],
                "data_source": "tasks",
                "handler": "query_tasks"
            },
            "find_meeting": {
                "required_fields": [],
                "optional_fields": ["participants", "timeframe", "topic"],
                "data_source": "calendar",
                "handler": "query_meetings"
            },
            "send_message": {
                "required_fields": ["receiver", "content"],
                "optional_fields": ["medium"],
                "data_source": None,
                "handler": "send_message"
            },
            "find_document": {
                "required_fields": [],
                "optional_fields": ["file_type", "sender", "timeframe"],
                "data_source": "files",
                "handler": "query_documents"
            },
        }

    def validate(
        self,
        detected_intent: Dict[str, Any],
        previous_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Validates AI-detected intent and fills missing data from previous context.
        Returns structured result ready for routing or clarification.
        """
        intent = detected_intent.get("intent", "unknown")
        entities = detected_intent.get("entities", {}) or {}
        confidence = detected_intent.get("confidence", 0.5)

        # 1️⃣ If AI generated a new/unknown intent, map it to the closest known one
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

        # 2️⃣ Try filling missing entities from context
        if previous_context:
            last_entities = previous_context.get("entities", {})
            for k, v in last_entities.items():
                if k not in entities:
                    entities[k] = v

        # 3️⃣ Validate required fields
        missing_fields = [f for f in schema["required_fields"] if f not in entities]

        if missing_fields:
            return {
                "status": "incomplete",
                "intent": intent,
                "missing_fields": missing_fields,
                "entities": entities,
                "message": self.generate_followup(intent, missing_fields)
            }

        # 4️⃣ Return structured command for routing
        return {
            "status": "ready",
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "handler": schema["handler"],
            "data_source": schema["data_source"]
        }

    # 🧠 NEW: Generate follow-up question for missing entities
    def generate_followup(self, intent: str, missing_fields: list[str]) -> str:
        """
        Generates a natural follow-up question to fill in missing info.
        """
        if not missing_fields:
            return ""

        questions = {
            "receiver": "Who would you like to send it to?",
            "content": "What message should I send?",
            "timeframe": "For what period should I check?",
            "type": "Do you mean a debit or credit transaction?",
            "subject": "Do you remember the subject of the email?",
            "participants": "Who was in the meeting?",
        }

        prompts = [questions.get(f, f"Can you provide {f}?") for f in missing_fields]
        followup = " ".join(prompts)

        return followup
