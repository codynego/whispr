# whispr/ai_core/message_handler.py
from .context_manager import ContextManager
from .intent_detector import IntentDetector
from .intent_schema_parser import IntentSchemaParser
from .intent_router import IntentRouter
from .llm_service import LLMService
from django.conf import settings
from typing import Dict, Any, Optional
import re
from celery import shared_task
from django.contrib.auth import get_user_model

APIKEY = settings.OPENAI_API_KEY


class MessageHandler:
    """
    Main entry point for processing user messages.
    Coordinates context, intent detection, channel detection, validation, routing, and response.
    """

    def __init__(self, user):
        print("Initializing MessageHandler for user ID:", user.id)
        self.user = user
        self.context_manager = ContextManager()
        self.intent_detector = IntentDetector()
        self.intent_schema_parser = IntentSchemaParser()
        self.intent_router = IntentRouter(self.user)
        self.llm = LLMService(self.user, APIKEY)

        # Known intents
        self.intents = [
            "read_message",
            "get_content",
            "find_message",
            "find_transaction",
            "find_meeting",
            "send_message",
            "find_document",
            "summarize_message",
            "automation_create",
            "automation_update",
            "automation_delete",
        ]

        # Required @commands for safety-critical actions
        self.required_commands = {
            "send_message": "@send",
            "summarize_message": "@summarize",
            "read_message": "@read",
            "automation_create": "@create_automation",
            "automation_update": "@update_automation",
            "automation_delete": "@delete_automation",
        }

    # --------------------------------------------------------
    # 🧠 HANDLE USER MESSAGE
    # --------------------------------------------------------
    def handle(self, message: str):
        """
        Handles an incoming message from the user.
        """
        # --- 1️⃣ Retrieve and merge context ---
        print("Retrieving and merging context for user ID:", self.user.id)
        previous_context = self.context_manager.get_context(self.user.id)
        merged_context = self.context_manager.merge(previous_context, message)

        # --- 3️⃣ Detect intent & entities ---
        print("getting intent data for message:", message)
        intent_data = self.intent_detector.detect_intent(user=self.user, message=message, previous_context=merged_context)
        print("Detected intent data:", intent_data)

        # --- 4️⃣ Detect or infer the channel ---
        # Try to infer channel based on message text, detected entities, or fallback
        channel = intent_data.get("channel")

        # --- 6️⃣ Enforce required @commands ---
        required_cmd = self.required_commands.get(intent_data["intent"])

        # --- 7️⃣ Validate schema completeness ---
        print("Validating intent schema for intent:", intent_data["intent"])
        validation_result = self.intent_schema_parser.validate(intent_data, merged_context)
        print("Validation result:", validation_result)

        # If intent is unclear or missing
        if intent_data["intent"] not in self.intents:
            ai_reply = self.llm.generate_reply(user_message=message, context_data=merged_context)
            self.context_manager.update_context(self.user.id, intent_data)

            return {
                "status": "unknown_intent",
                "reply": ai_reply,
                "intent": intent_data,
            }

        print("Validation result:", "got here")
        contexty = self.context_manager.get_context(self.user.id)
        print("Current context after update:", contexty)

        # --- 8️⃣ Handle incomplete schema ---
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

        # --- 9️⃣ Route to the correct handler ---
        handler = self.intent_router.get_handler(intent_data["intent"])
        if not handler:
            return {
                "status": "error",
                "reply": f"I couldn’t find how to handle '{intent_data['intent']}'.",
                "intent": intent_data["intent"],
            }
        result = handler(intent_data.get("entities"), channel=intent_data.get("channel"))

        # --- 🔟 Generate AI reply with channel context ---
        ai_reply = self.llm.generate_reply(user_message=message, task_result=result, context_data=merged_context)
        self.context_manager.update_context(self.user.id, intent_data)

        return {
            "status": "success",
            "reply": ai_reply,
            "intent": intent_data["intent"],
            "channel": channel,
            "data": result,
        }


@shared_task(bind=True, max_retries=3)
def process_message(self, user_id: int, message: str) -> Dict[str, Any]:
    """
    Celery shared task for asynchronously processing user messages.
    This wraps the MessageHandler to allow distributed execution.
    """
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return {
            "status": "error",
            "reply": "User not found. Please check your session.",
        }

    handler = MessageHandler(user)
    result = handler.handle(message)

    # Optional: Log task completion or handle retries if needed
    if self.request.retries > 0:
        print(f"Task retry {self.request.retries} for user {user_id}")

    return result