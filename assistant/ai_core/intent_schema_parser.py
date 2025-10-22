# from typing import Dict, Any, Optional
# import difflib

# class IntentSchemaParser:
#     """
#     Validates detected intents against predefined schemas and ensures
#     all required entities are available before routing.
#     Supports dynamic fallback for AI-detected (Gemini) intents.
#     """

#     def __init__(self):
#        self.intent_schemas = {
#             "read_message": {
#                 "required_fields": [],  # sender or query_text can now trigger retrieval
#                 "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],  # semantic-aware search
#                 "data_source": "emails",
#                 "handler": "read_message"
#             },
#             "find_message": {
#                 "required_fields": [],  # no hard requirement; can search by filters or query
#                 "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],  # allow embeddings-based query
#                 "data_source": "emails",
#                 "handler": "query_messages"
#             },
#             "find_transaction": {
#                 "required_fields": ["type"],
#                 "optional_fields": ["timeframe", "amount"],
#                 "data_source": "transactions",
#                 "handler": "query_transactions"
#             },
#             "find_task": {
#                 "required_fields": [],
#                 "optional_fields": ["status", "priority", "timeframe"],
#                 "data_source": "tasks",
#                 "handler": "query_tasks"
#             },
#             "find_meeting": {
#                 "required_fields": [],
#                 "optional_fields": ["participants", "timeframe", "topic"],
#                 "data_source": "calendar",
#                 "handler": "query_meetings"
#             },
#             "send_message": {
#                 "required_fields": [],
#                 "optional_fields": ["receiver", "receiver_message", "subject", "body"],
#                 "data_source": None,
#                 "handler": "send_message"
#             },
#             "find_document": {
#                 "required_fields": [],
#                 "optional_fields": ["file_type", "sender", "timeframe"],
#                 "data_source": "files",
#                 "handler": "query_documents"
#             },
#             "summarize_message": {
#                 "required_fields": [],  # sender or query_text triggers summary
#                 "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],
#                 "data_source": "emails",
#                 "handler": "summarize_message"
#             },
#         }


#     def validate(
#         self,
#         detected_intent: Dict[str, Any],
#         previous_context: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """
#         Validates AI-detected intent and fills missing data from previous context.
#         Returns structured result ready for routing or clarification.
#         """
#         intent = detected_intent.get("intent", "unknown")
#         entities = detected_intent.get("entities", {}) or {}
#         confidence = detected_intent.get("confidence", 0.5)

#         # 1️⃣ If AI generated a new/unknown intent, map it to the closest known one
#         if intent not in self.intent_schemas:
#             possible_match = difflib.get_close_matches(intent, self.intent_schemas.keys(), n=1, cutoff=0.6)
#             if possible_match:
#                 intent = possible_match[0]
#             else:
#                 return {
#                     "status": "unknown_intent",
#                     "intent": intent,
#                     "confidence": confidence,
#                     "message": f"Sorry, I’m not sure how to handle '{intent}'."
#                 }

#         schema = self.intent_schemas[intent]

#         # 2️⃣ Try filling missing entities from context
#         if previous_context:
#             last_entities = previous_context.get("entities", {})
#             for k, v in last_entities.items():
#                 if k not in entities:
#                     entities[k] = v

#         # 3️⃣ Validate required fields
#         missing_fields = [f for f in schema["required_fields"] if f not in entities]

#         if missing_fields:
#             return {
#                 "status": "incomplete",
#                 "intent": intent,
#                 "missing_fields": missing_fields,
#                 "entities": entities,
#                 "message": self.generate_followup(intent, missing_fields)
#             }

#         # 4️⃣ Return structured command for routing
#         return {
#             "status": "ready",
#             "intent": intent,
#             "confidence": confidence,
#             "entities": entities,
#             "handler": schema["handler"],
#             "data_source": schema["data_source"]
#         }

#     # 🧠 NEW: Generate follow-up question for missing entities
#     def generate_followup(self, intent: str, missing_fields: list[str]) -> str:
#         """
#         Generates a natural follow-up question to fill in missing info.
#         """
#         if not missing_fields:
#             return ""

#         questions = {
#             "receiver": "Who would you like to send it to?",
#             "content": "What message should I send?",
#             "timeframe": "For what period should I check?",
#             "type": "Do you mean a debit or credit transaction?",
#             "subject": "Do you remember the subject of the email?",
#             "participants": "Who was in the meeting?",
#         }

#         prompts = [questions.get(f, f"Can you provide {f}?") for f in missing_fields]
#         followup = " ".join(prompts)

#         return followup



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
            # --- Email-related ---
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
            "send_message": {
                "required_fields": [],
                "optional_fields": ["receiver", "receiver_message", "subject", "body"],
                "data_source": None,
                "handler": "send_message"
            },
            "summarize_message": {
                "required_fields": [],
                "optional_fields": ["sender", "category", "timeframe", "subject", "query_text"],
                "data_source": "emails",
                "handler": "summarize_message"
            },

            # --- WhatsApp / Chat-related ---
            "send_message": {
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

            # --- Calendar / Tasks / Misc ---
            "find_meeting": {
                "required_fields": [],
                "optional_fields": ["participants", "timeframe", "topic"],
                "data_source": "calendar",
                "handler": "query_meetings"
            },
            "find_task": {
                "required_fields": [],
                "optional_fields": ["status", "priority", "timeframe"],
                "data_source": "tasks",
                "handler": "query_tasks"
            },
            "find_document": {
                "required_fields": [],
                "optional_fields": ["file_type", "sender", "timeframe"],
                "data_source": "files",
                "handler": "query_documents"
            },
            "find_transaction": {
                "required_fields": ["type"],
                "optional_fields": ["timeframe", "amount"],
                "data_source": "transactions",
                "handler": "query_transactions"
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
