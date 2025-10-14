# whispr/ai_core/message_handler.py
from .context_manager import ContextManager
from .intent_detector import IntentDetector
from .intent_schema_parser import IntentSchemaParser
from .intent_router import IntentRouter
from .llm_service import LLMService
from django.conf import settings
from typing import Dict, Any, Optional
import re

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
        self.llm = LLMService(self.user, APIKEY)

        # Known intents
        self.intents = [
            "read_email",
            "get_content",
            "find_email",
            "find_transaction",
            "find_task",
            "find_meeting",
            "send_message",
            "find_document",
            "summarize_email",
        ]

        # Required @commands for safety-critical actions
        self.required_commands = {
            "send_message": "@send",
            "create_task": "@task",
            "summarize_email": "@summarize",
            "read_email": "@read",
        }

    # --------------------------------------------------------
    # 🧠 HANDLE USER MESSAGE
    # --------------------------------------------------------
    def handle(self, message: str):
        """
        Handles an incoming message from the user.
        """
        # --- 1️⃣ Retrieve and merge context ---
        previous_context = self.context_manager.get_context(self.user.id)
        merged_context = self.context_manager.merge(previous_context, message)
        print("Merged Context:", merged_context)

        # --- 2️⃣ Detect @command in message ---
        command_match = re.search(r"(@\w+)", message)
        user_command = command_match.group(1).lower() if command_match else None
        print("Detected command:", user_command)

        # --- 3️⃣ Detect intent & entities ---
        intent_data = self.intent_detector.detect_intent(message, merged_context)
        print("Detected intent data:", intent_data)

        # --- 4️⃣ Enforce required @commands ---
        required_cmd = self.required_commands.get(intent_data["intent"])
        if required_cmd and required_cmd != user_command:
            clarification = (
                f"Please include '{required_cmd}' in your message to confirm this action.\n"
                f"Example: {required_cmd} Send a message to John saying 'I’ll be late'."
            )
            return {
                "status": "confirmation_needed",
                "reply": clarification,
                "intent": intent_data["intent"],
                "expected_command": required_cmd,
            }

        # --- 5️⃣ Validate schema completeness ---
        validation_result = self.intent_schema_parser.validate(intent_data, previous_context)

        # Missing or unclear intent
        if intent_data["intent"] not in self.intents:
            # prompt = (
            #     f"The user said: '{message}'. use the context to identify their intent. If unclear, and use this data {merged_context} to respond naturally. If you can't identify the intent, just say 'I'm not sure what you mean. Could you clarify?'. Please"
            #     f"respond briefly asking for clarification, but don’t mention AI or system details."
            # )
            ai_reply = self.llm.generate_reply(message, context_data=merged_context)
            self.context_manager.update_context(self.user.id, intent_data)
            return {
                "status": "unknown_intent",
                "reply": ai_reply,
                "intent": intent_data,
            }

        # Missing fields
        if validation_result["status"] == "incomplete":
            ai_reply = self.llm.ask_for_missing_info(
                intent_data["intent"],
                validation_result.get("missing_fields", []),
                intent_data.get("entities", {}),
            )
            self.context_manager.update_context(self.user.id, intent_data)
            return {
                "status": "clarification_needed",
                "reply": ai_reply,
                "missing": validation_result.get("missing_fields", []),
                "intent": intent_data["intent"],
            }

        # --- 6️⃣ Route to correct handler ---
        handler = self.intent_router.get_handler(intent_data["intent"])
        if not handler:
            print("No handler found for intent:", intent_data["intent"])
            return {
                "status": "error",
                "reply": f"I couldn’t find how to handle '{intent_data['intent']}'.",
                "intent": intent_data["intent"],
            }

        result = handler(intent_data.get("entities", {}))
        print("Handler result:", result)

        # --- 7️⃣ Generate AI reply ---
        ai_reply = self.llm.generate_reply(message, result)
        self.context_manager.update_context(self.user.id, intent_data)

        return {
            "status": "success",
            "reply": ai_reply,
            "intent": intent_data["intent"],
            "data": result,
        }
