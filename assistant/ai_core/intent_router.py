# assistant/intent_router.py
from unified.services import MessageService
from .llm_service import LLMService
from django.conf import settings
from assistant.automation_service import AutomationService
from .context_manager import ContextManager
from assistant.models import Automation

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
        if entities.get("__should_create_automation__"):
            intent = "automation_create"

        handler = self.get_handler(intent)
        if not handler:
            return "🤔 Sorry, I couldn’t understand that request."

        try:
            return handler(entities, channel)
        except Exception as e:
            return f"❌ Something went wrong while processing '{intent}': {e}"

    # ---------------- INTENT DETECTION ---------------- #
    def _detect_intent(self, message, context=None):
        parsed = self.llm_service.parse_intent_and_entities(message, context)
        intent = parsed.get("intent", "unknown")
        entities = parsed.get("entities", {})
        return intent, entities

    def _detect_channel(self, message: str):
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
        service = self._get_service(channel)
        if not service:
            return "⚠️ No matching channel found."
        summary = service.summarize_message(
            sender=entities.get("sender"),
            query_text=entities.get("query_text"),
        )
        return f"🧠 Summary:\n{summary}" if summary else "Couldn't summarize this message."

    # ---------------- AUTOMATION HANDLERS ---------------- #
    def handle_create_automation(self, entities, channel="all"):
        """
        Create automation using workflow JSON instead of single action_type/action_params.
        """
        print("Creating automation with entities:", entities)
        workflow = entities.get("workflow")
        if not workflow:
            return "⚠️ No workflow provided for automation."

        service = AutomationService(self.user)
        print("Workflow for automation:", workflow)
        automation = service.create_automation(
            name=entities.get("name"),
            workflow=workflow,
            trigger_type=entities.get("trigger_type"),
            next_run_at=entities.get("next_run_at"),
            recurrence_pattern=entities.get("recurrence_pattern"),
            description=entities.get("description"),
            is_active=entities.get("is_active", True),
        )
        print("Created automation:", automation)
        if not automation:
            return "❌ Failed to create automation."
        return f"⚡ Automation '{automation.name}' created successfully."

    def handle_update_automation(self, entities, channel="all"):
        service = AutomationService(self.user)
        automation_id = entities.get("automation_id") or entities.get("task_id")
        if not automation_id:
            return "⚠️ I couldn’t identify which automation to update."

        updates = {
            "name": entities.get("name"),
            "description": entities.get("description"),
            "trigger_type": entities.get("trigger_type"),
            "workflow": entities.get("workflow"),
            "is_active": entities.get("is_active"),
            "next_run_at": entities.get("next_run_at"),
            "recurrence_pattern": entities.get("recurrence_pattern"),
        }
        updates = {k: v for k, v in updates.items() if v is not None}

        automation = service.update_automation(automation_id, **updates)
        return "✅ Automation updated successfully." if automation else "❌ Failed to update automation."

    def handle_delete_automation(self, entities, channel="all"):
        service = AutomationService(self.user)
        automation_id = entities.get("automation_id") or entities.get("task_id")
        if not automation_id:
            return "⚠️ I couldn’t find which automation to delete."

        success = service.delete_automation(automation_id)
        return "🗑️ Automation deleted successfully." if success else "❌ Could not delete automation."

    # ---------------- SERVICE RESOLVER ---------------- #
    def _get_service(self, channel):
        return self.message_service
