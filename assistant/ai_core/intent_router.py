# assistant/intent_router.py
from unified.services import MessageService
from .llm_service import LLMService
from django.conf import settings
from assistant.automation_service import AutomationService
from .context_manager import ContextManager
from assistant.models import Automation
from .intent_schema_parser import IntentSchemaParser  # From earlier updates
from datetime import datetime, timedelta
import pytz  # For timezone handling
import logging

logger = logging.getLogger(__name__)
APIKEY = settings.GEMINI_API_KEY


# Stub services (extend with real implementations)
class TaskService:
    @staticmethod
    def create_task(title, due_datetime, description=""):
        # Placeholder: Integrate with your task backend (e.g., Todoist)
        logger.info(f"Created task: {title} due {due_datetime}")
        return f"Task '{title}' created for {due_datetime}."

    @staticmethod
    def set_reminder(title, next_run_at, description=""):
        # Placeholder: Similar to tasks
        logger.info(f"Set reminder: {title} at {next_run_at}")
        return f"Reminder '{title}' set for {next_run_at}."


class CalendarService:
    @staticmethod
    def create_event(event_title, timeframe, participants=None, location=None):
        # Placeholder: Integrate with Google Calendar API
        logger.info(f"Created event: {event_title} at {timeframe}")
        return f"Event '{event_title}' scheduled."

    @staticmethod
    def find_meetings(participants=None, timeframe=None):
        # Placeholder
        return "No meetings found."  # Or fetch real data


class InsightService:
    @staticmethod
    def generate_insights(query_text, timeframe=None):
        # Placeholder: Use LLM for analysis
        logger.info(f"Generating insights for: {query_text}")
        return f"Insights for '{query_text}': [Generated summary]."


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
        self.task_service = TaskService() 
        self.calendar_service = CalendarService()  # New: For events
        self.insight_service = InsightService()  # New: For insights
        self.context_manager = ContextManager()
        self.intent_parser = IntentSchemaParser()  # New: For validation
        self.handlers = self._register_handlers()

    # ---------------- REGISTER HANDLERS ---------------- #
    def _register_handlers(self):
        return {
            "read_message": self.handle_read_message,
            "find_message": self.handle_find_messages,
            "send_message": self.handle_send_message,
            "reply_message": self.handle_reply_message,
            "summarize_message": self.handle_summarize_message,
            "insights": self.handle_insights,  # New
            "create_event": self.handle_create_event,  # New

            # automation system
            "automation_create": self.handle_create_automation,
            "automation_update": self.handle_update_automation,
            "automation_delete": self.handle_delete_automation,
        }

    # ---------------- MAIN ENTRY ---------------- #
    def route(self, message, context=None):
        """
        1️⃣ Use LLM to detect intent & entities
        2️⃣ Validate with schema parser
        3️⃣ Auto-upgrade to automation_create if trigger flag is present
        4️⃣ Route to correct handler
        """
        intent_data = self._detect_intent(message, context)
        intent = intent_data.get("intent", "unknown")
        entities = intent_data.get("entities", {})

        # Validate with schema
        validation = self.intent_parser.validate(intent_data, context)
        if validation["status"] == "incomplete":
            self.context_manager.update_context(self.user.id, validation)
            return f"🤔 To complete this, please provide: {validation['message']}"

        channel = entities.get("channel") or self._detect_channel(message)
        data_source = validation.get("data_source", "all")

        # Auto-upgrade to automation_create if trigger flag is present
        if entities.get("__should_create_automation__"):
            intent = "automation_create"

        handler = self.get_handler(intent)
        if not handler:
            return "🤔 Sorry, I couldn’t understand that request."

        try:
            result = handler(entities, channel, data_source)
            # Update context with result
            intent_data.update({"result": result})
            self.context_manager.update_context(self.user.id, intent_data)
            return result
        except Exception as e:
            logger.error(f"Handler error for {intent}: {e}")
            return f"❌ Something went wrong while processing '{intent}': {e}"

    # ---------------- INTENT DETECTION ---------------- #
    def _detect_intent(self, message, context=None):
        parsed = self.llm_service.parse_intent_and_entities(message, context)
        return parsed  # Returns dict with 'intent', 'entities', etc.

    def _detect_channel(self, message: str):
        msg_lower = message.lower()
        if "email" in msg_lower or "inbox" in msg_lower:
            return "email"
        elif "whatsapp" in msg_lower or "chat" in msg_lower:
            return "whatsapp"
        elif "sms" in msg_lower:
            return "sms"
        elif "calendar" in msg_lower or "meeting" in msg_lower:
            return "calendar"
        elif "task" in msg_lower or "reminder" in msg_lower:
            return "tasks"
        return "all"

    def get_handler(self, intent):
        return self.handlers.get(intent)

    # ---------------- HANDLER METHODS ---------------- #
    def handle_find_messages(self, entities, channel="all", data_source="all"):
        service = self._get_service(channel, data_source)
        if not service:
            return "⚠️ No matching channel found."
        results = service.find_messages(
            sender=entities.get("sender"),
            subject=entities.get("subject"),
            date=entities.get("timeframe"),
            query_text=entities.get("query_text"),
        )
        return results or f"No {channel} messages found."

    def handle_read_message(self, entities, channel="all", data_source="all"):
        service = self._get_service(channel, data_source)
        if not service:
            return "⚠️ No matching channel found."
        result = service.read_message(
            sender=entities.get("sender"),
            query_text=entities.get("query_text"),
        )
        return result or f"No {channel} message found."

    def handle_send_message(self, entities, channel="all", data_source="all"):
        service = self._get_service(channel, data_source)
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

    def handle_reply_message(self, entities, channel="all", data_source="all"):
        service = self._get_service(channel, data_source)
        if not service:
            return "⚠️ No matching channel found."
        success = service.reply_to_message(
            message_id=entities.get("message_id"),
            body=entities.get("body"),
        )
        return "💬 Reply sent successfully." if success else "❌ Failed to send reply."

    def handle_summarize_message(self, entities, channel="all", data_source="all"):
        service = self._get_service(channel, data_source)
        if not service:
            return "⚠️ No matching channel found."
        summary = service.summarize_message(
            sender=entities.get("sender"),
            query_text=entities.get("query_text"),
        )
        return f"🧠 Summary:\n{summary}" if summary else "Couldn't summarize this message."

    # ---------------- NEW HANDLERS ---------------- #
    def handle_create_task(self, entities, channel="all", data_source="tasks"):
        service = self._get_service(channel, data_source)
        result = service.create_task(
            title=entities.get("task_title"),
            due_datetime=entities.get("next_run_at") or entities.get("due_datetime"),
            description=entities.get("description"),
        )
        return result

    def handle_set_reminder(self, entities, channel="all", data_source="tasks"):
        service = self._get_service(channel, data_source)
        result = service.set_reminder(
            title=entities.get("name") or entities.get("task_title"),
            next_run_at=entities.get("next_run_at"),
            description=entities.get("description"),
        )
        return result

    def handle_insights(self, entities, channel="all", data_source="insights"):
        service = self._get_service(channel, data_source)
        insights = service.generate_insights(
            query_text=entities.get("query_text"),
            timeframe=entities.get("timeframe"),
        )
        return f"🔍 Insights:\n{insights}"

    def handle_create_event(self, entities, channel="all", data_source="calendar"):
        service = self._get_service(channel, data_source)
        result = service.create_event(
            event_title=entities.get("event_title"),
            timeframe=entities.get("timeframe"),
            participants=entities.get("participants"),
            location=entities.get("location"),
        )
        return result

    # ---------------- AUTOMATION HANDLERS ---------------- #
    def handle_create_automation(self, entities, channel="all", data_source="automations"):
        """
        Create automation using full workflow JSON.
        Computes next_run_at based on trigger/recurrence (e.g., next Monday).
        """
        workflow = entities.get("workflow")
        if not workflow:
            return "⚠️ No workflow provided for automation."

        # Compute next_run_at (example for on_schedule; extend for others)
        next_run_at = self._get_next_run_at(entities)
        trigger_condition = workflow.get("trigger", {}).get("config", {})

        service = AutomationService(self.user)
        automation = service.create_automation(
            name=entities.get("name"),
            workflow=workflow,  # Full workflow to action_params
            trigger_type=entities.get("trigger_type"),
            trigger_condition=trigger_condition,
            next_run_at=next_run_at,
            recurrence_pattern=entities.get("recurrence_pattern"),
            description=entities.get("description"),
            is_active=entities.get("is_active", True),
        )
        if not automation:
            return "❌ Failed to create automation."
        logger.info(f"Created automation '{automation.name}' (ID: {automation.id})")
        return f"⚡ Automation '{automation.name}' created successfully. Next run: {next_run_at}."

    def _get_next_run_at(self, entities):
        """Get or compute next_run_at from entities (prefers explicit, then recurrence, then default)."""
        next_run_str = entities.get("next_run_at")
        if next_run_str:
            try:
                # Handle ISO string with Z (Python 3.10 compatibility)
                dt_str = next_run_str.replace('Z', '+00:00') if next_run_str.endswith('Z') else next_run_str
                return datetime.fromisoformat(dt_str)
            except ValueError as e:
                logger.warning(f"Invalid next_run_at format '{next_run_str}': {e}. Falling back to computation.")

        # Compute from recurrence if present
        recurrence = (entities.get("recurrence_pattern") or "").lower()
        if recurrence:
            today = datetime.now(pytz.timezone('Africa/Lagos'))
            trigger_config = entities.get("workflow", {}).get("trigger", {}).get("config", {})

            if "monday" in recurrence and "weekly" in recurrence:
                # Next Monday after today
                days_ahead = (7 - today.weekday()) % 7
                if days_ahead == 0:  # Today is Monday
                    days_ahead = 7
                next_monday = today + timedelta(days=days_ahead)
                time_str = trigger_config.get("time", "11:00")
                try:
                    hour, minute = map(int, time_str.split(":"))
                except (ValueError, AttributeError):
                    hour, minute = 11, 0
                return next_monday.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # TODO: Add logic for daily, tuesday, monthly, etc.
            # For now, fallback to today at config time
            logger.warning(f"Unsupported recurrence pattern: {recurrence}. Using today.")

        # Final fallback: today at default time from config
        today = datetime.now(pytz.timezone('Africa/Lagos'))
        trigger_config = entities.get("workflow", {}).get("trigger", {}).get("config", {})
        time_str = trigger_config.get("time", "09:00")
        try:
            hour, minute = map(int, time_str.split(":"))
        except (ValueError, AttributeError):
            hour, minute = 9, 0
        return today.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def handle_update_automation(self, entities, channel="all", data_source="automations"):
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

    def handle_delete_automation(self, entities, channel="all", data_source="automations"):
        service = AutomationService(self.user)
        automation_id = entities.get("automation_id") or entities.get("task_id")
        if not automation_id:
            return "⚠️ I couldn’t find which automation to delete."

        success = service.delete_automation(automation_id)
        return "🗑️ Automation deleted successfully." if success else "❌ Could not delete automation."

    # ---------------- SERVICE RESOLVER ---------------- #
    def _get_service(self, channel, data_source):
        """Dynamic service based on channel/data_source."""
        mappings = {
            "email": self.message_service,
            "whatsapp": self.message_service,
            "calendar": self.calendar_service,
            "tasks": self.task_service,
            "insights": self.insight_service,
        }
        return mappings.get(channel) or mappings.get(data_source) or self.message_service