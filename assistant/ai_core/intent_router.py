# assistant/intent_router.py

from unified.services import MessageService
from .llm_service import LLMService
from django.conf import settings
from assistant.automation_service import AutomationService  # ✅ new service
from .context_manager import ContextManager

APIKEY = settings.GEMINI_API_KEY


class IntentRouter:
    """
    Routes natural language user inputs to the correct handler.
    Detects user intent (e.g., summarize, send, automate reminders)
    and executes it through unified services.
    """

    def __init__(self, user=None):
        self.user = user
        self.llm_service = LLMService(user, APIKEY)
        self.message_service = MessageService(user)
        self.context_manager = ContextManager()
        self.handlers = self._register_handlers()

    # ---------------- REGISTER HANDLERS ---------------- #
    def _register_handlers(self):
        return {
            "read_message": self.handle_read_message,
            "find_message": self.handle_find_messages,
            "send_message": self.handle_send_message,
            "reply_message": self.handle_reply_message,
            "summarize_message": self.handle_summarize_message,

            # automation system
            "automation_create": self.handle_create_automation,
            "automation_update": self.handle_update_automation,
            "automation_delete": self.handle_delete_automation,
        }

    # ---------------- MAIN ENTRY ---------------- #
    def route(self, message, context=None):
        """
        1️⃣ Use LLM to detect intent & entities
        2️⃣ Adjust if automation trigger is requested
        3️⃣ Route to correct handler
        """
        intent, entities = self._detect_intent(message, context)
        channel = entities.get("channel") or self._detect_channel(message)

        # Auto-upgrade to automation_create if trigger flag is present
        if entities.get("__should_create_trigger__"):
            intent = "automation_create"

        handler = self.get_handler(intent)
        if not handler:
            return f"🤔 Sorry, I couldn’t understand that request."

        try:
            return handler(entities, channel)
        except Exception as e:
            return f"❌ Something went wrong while processing '{intent}': {e}"

    # ---------------- INTENT DETECTION ---------------- #
    def _detect_intent(self, message, context=None):
        """Uses LLM to infer intent & entities."""
        parsed = self.llm_service.parse_intent_and_entities(message, context)
        intent = parsed.get("intent", "unknown")
        entities = parsed.get("entities", {})
        return intent, entities

    def _detect_channel(self, message: str):
        """Heuristic for guessing communication channel."""
        msg_lower = message.lower()
        if "email" in msg_lower or "inbox" in msg_lower:
            return "email"
        elif "whatsapp" in msg_lower or "chat" in msg_lower:
            return "whatsapp"
        elif "sms" in msg_lower:
            return "sms"
        return "all"

    def get_handler(self, intent):
        return self.handlers.get(intent)

    # ---------------- HANDLER METHODS ---------------- #
    def handle_find_messages(self, entities, channel="all"):
        intent_data = {
            "intent": "find_message",
            "entities": entities,
            "channel": channel,
            "message": entities.get("query_text"),
        }
        self.context_manager.update_context(self.user.id, intent_data)

        service = self._get_service(channel)
        if not service:
            return "⚠️ No matching channel found."

        results = service.find_messages(
            sender=entities.get("sender"),
            subject=entities.get("subject"),
            date=entities.get("timeframe"),
            query_text=entities.get("query_text"),
        )
        return results or f"No {channel} messages found."

    def handle_read_message(self, entities, channel="all"):
        service = self._get_service(channel)
        if not service:
            return "⚠️ No matching channel found."
        result = service.read_message(
            sender=entities.get("sender"),
            query_text=entities.get("query_text"),
        )
        return result or f"No {channel} message found."

    def handle_send_message(self, entities, channel="all"):
        service = self._get_service(channel)
        if not service:
            return "⚠️ No matching channel found."
        success = service.send_message(
            receiver_name=entities.get("receiver_name"),
            receiver=entities.get("receiver") or entities.get("receiver_number"),
            subject=entities.get("subject"),
            body=entities.get("body"),
            channel=channel,
        )
        return "✅ Message sent successfully." if success else "❌ Failed to send message."

    def handle_reply_message(self, entities, channel="all"):
        service = self._get_service(channel)
        if not service:
            return "⚠️ No matching channel found."
        success = service.reply_to_message(
            message_id=entities.get("message_id"),
            body=entities.get("body"),
        )
        return "💬 Reply sent successfully." if success else "❌ Failed to send reply."

    def handle_summarize_message(self, entities, channel="all"):
        """Summarizes one or more messages."""
        service = self._get_service(channel)
        if not service:
            return "⚠️ No matching channel found."
        summary = service.summarize_message(
            sender=entities.get("sender"),
            query_text=entities.get("query_text"),
        )
        return f"🧠 Summary:\n{summary}" if summary else "Couldn't summarize this message."

    def handle_create_automation(self, entities, channel="all"):
        """
        Creates a new automation or scheduled trigger.
        """
        print("about to run some create automation")
        automation = AutomationService(self.user).create_automation(
            task_type=entities.get("task_type"),
            title=entities.get("task_title"),
            trigger_type=entities.get("trigger_type"),
            due_datetime=entities.get("due_datetime"),
            is_recurring=entities.get("is_recurring", False),
            recurrence_pattern=entities.get("recurrence_pattern"),
            metadata=entities,
        )
        if not automation:
            return "❌ Failed to create automation."
        return f"⚡ Automation '{automation.task_type}' created successfully."


    def handle_update_automation(self, entities, channel="all"):
        """
        Updates an existing automation’s details.
        Example: “Change my daily summary to 8AM.”
        """
        service = AutomationService(self.user)
        automation_id = entities.get("automation_id") or entities.get("task_id")
        if not automation_id:
            return "⚠️ I couldn’t identify which automation to update."

        success = service.update_automation(
            automation_id=automation_id,
            updates={
                "task_type": entities.get("task_type"),
                "title": entities.get("task_title"),
                "due_datetime": entities.get("due_datetime"),
                "recurrence_pattern": entities.get("recurrence_pattern"),
            },
        )
        return "✅ Automation updated successfully." if success else "❌ Failed to update automation."


    def handle_delete_automation(self, entities, channel="all"):
        """
        Cancels or deletes a scheduled automation.
        Example: “Cancel my follow-up reminder.”
        """
        service = AutomationService(self.user)
        automation_id = entities.get("automation_id") or entities.get("task_id")

        if not automation_id and not entities.get("task_type"):
            return "⚠️ I couldn’t find which automation to delete."

        success = service.delete_automation(
            automation_id=automation_id,
            task_type=entities.get("task_type"),
        )
        return "🗑️ Automation deleted successfully." if success else "❌ Could not delete automation."


    # ---------------- SERVICE RESOLVER ---------------- #
    def _get_service(self, channel):
        return self.message_service
