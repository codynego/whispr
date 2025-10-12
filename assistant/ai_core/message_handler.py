# whispr/ai_core/message_handler.py
from .context_manager import ContextManager
from .intent_detector import IntentDetector
from .intent_schema_parser import IntentSchemaParser
from .intent_router import IntentRouter
from .llm_service import LLMService
from django.conf import settings
from typing import Dict, Any, Optional
# from .kg_service import KnowledgeGraph
APIKEY = settings.GEMINI_API_KEY

class MessageHandler:
    """
    Main entry point for processing user messages.
    Coordinates context, intent detection, validation, routing, and response.
    """

    def __init__(self, user):
        self.user = user
        self.context_manager = ContextManager()
        self.intent_detector = IntentDetector()
        self.intent_schema_parser = IntentSchemaParser()
        self.intent_router = IntentRouter(self.user)
        # self.kg = KnowledgeGraph()
        self.llm = LLMService(self.user, APIKEY)
        self.intents = [
            "read_message",
            "get_content",
            "find_email",
            "find_transaction",
            "find_task",
            "find_meeting",
            "send_message",
            "find_document"
        ]

    def handle(self, message: str):
        """
        Handles an incoming message from the user.
        """
        # 1️⃣ Retrieve and merge context
        previous_context = self.context_manager.get_context(self.user.id)
        merged_context = self.context_manager.merge(previous_context, message)
        print("Merged Context:", merged_context)

        # 2️⃣ Detect intent
        intent_data = self.intent_detector.detect_intent(message, merged_context)

        # 3️⃣ Validate schema (check if info is complete)
        validation_result = self.intent_schema_parser.validate(intent_data, previous_context)

        # 4️⃣ If info is missing → ask for clarification
        if intent_data["intent"] not in self.intents:
            prompt = f"you are an AI assistant. The user said {message} but you are not sure what they want, you can only respond with a short reply asking them to clarify what they want, do not mention that you are an AI model or anything about AI, just ask them to clarify what they want"
            ai_reply = self.llm.generate_reply(
                prompt,
                context_data=merged_context
            )
            self.context_manager.update_context(self.user.id, intent_data)
            return {
                "status": "unknown_intent",
                "reply": ai_reply,
                "intent": intent_data
            }
        if intent_data["intent"] in self.intents and validation_result["status"] == "incomplete":
            follow_up_prompt = f"provide a follow up reply to this message {message} and include this information, you can ask follow up questions for validation {validation_result}"
            ai_reply = self.llm.ask_for_missing_info(
                intent_data["intent"],
                validation_result.get("missing_fields", []),
                intent_data["entities"],
                context_data=merged_context
            )
            self.context_manager.update_context(self.user.id, intent_data)
            print("validation_result:", validation_result)
            return {
                "status": "clarification_needed",
                "reply": ai_reply,
                "missing": validation_result.get("missing_fields", []),
                "intent": intent_data["intent"]
            }

        handler = self.intent_router.get_handler(intent_data["intent"])
        print("Handler found:", handler)
        if not handler:
            print("No handler found for intent:", intent_data["intent"])
        result = handler(intent_data["entities"])
        print("Handler result:", result)

        ai_reply = self.llm.generate_reply( message, result)
        self.context_manager.update_context(self.user.id, intent_data)

        return {
            "status": "success",
            "reply": ai_reply,
            "intent": intent_data["intent"],
            "data": result
        }
