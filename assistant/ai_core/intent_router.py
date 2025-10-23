# from emails.services import EmailService
# from .llm_service import LLMService
# from django.conf import settings
# from assistant.models import AssistantTask

# APIKEY = settings.GEMINI_API_KEY


# class IntentRouter:
#     """
#     Routes user intents or @commands to the appropriate handler.
#     Supports both LLM-inferred intents and explicit @commands.
#     """

#     def __init__(self, user=None):
#         self.user = user
#         self.llm_service = LLMService(self.user, APIKEY)
#         self.email_service = EmailService(user=user)
#         self.handlers = self._register_handlers()
#         self.command_map = {
#             "@read": "read_email",
#             "@find": "find_email",
#             "@send": "send_email",
#             "@reply": "reply_email",
#             "@summarize": "summarize_email",
#             "@task": "create_task",
#             "@todo": "create_task",
#             "@remind": "create_task",
#         }

#     # ---------------- REGISTER HANDLERS ---------------- #
#     def _register_handlers(self):
#         return {
#             "get_content": self.handle_read_email,
#             "read_email": self.handle_read_email,
#             "find_email": self.handle_find_emails,
#             "find_emails": self.handle_find_emails,
#             "send_email": self.handle_send_email,
#             "reply_email": self.handle_reply_email,
#             "summarize_email": self.handle_summarize_email,
#             "create_task": self.handle_create_task,
#         }

#     # ---------------- GET HANDLER ---------------- #
#     def get_handler(self, intent_name):
#         return self.handlers.get(intent_name)

#     # ---------------- MAIN ENTRY ---------------- #
#     def route(self, message, context=None):
#         """
#         Main entry:
#         1. Checks for explicit @commands first
#         2. If none, uses LLM to infer intent
#         3. Routes to matching handler
#         """
#         intent, entities = self._detect_intent(message, context)

#         handler = self.get_handler(intent)
#         if not handler:
#             return f"Unknown or unsupported intent: '{intent}'"

#         try:
#             return handler(entities)
#         except Exception as e:
#             print(f"[IntentRouter] Error handling '{intent}':", e)
#             return f"An error occurred while processing '{intent}'."

#     # ---------------- INTENT DETECTION ---------------- #
#     def _detect_intent(self, message, context=None):
#         # 1️⃣ Check for explicit command (e.g. "@find mail from ALX")
#         for cmd, intent in self.command_map.items():
#             if cmd in message.lower():
#                 entities = self.llm_service.extract_entities(message, intent)
#                 return intent, entities

#         # 2️⃣ Fall back to LLM parsing
#         parsed = self.llm_service.parse_intent_and_entities(message, context)
#         intent = parsed.get("intent", "unknown")
#         entities = parsed.get("entities", {})
#         return intent, entities

#     # ---------------- HANDLER METHODS ---------------- #
#     def handle_find_emails(self, entities):
#         print("Finding emails with entities:", entities)
#         emails = self.email_service.find_emails(
#             sender=entities.get("sender"),
#             subject=entities.get("subject"),
#             date=entities.get("timeframe"),
#             query_text=entities.get("query_text"),
#         )
#         return emails or "No emails found matching your query."

#     def handle_create_task(self, entities):
#         print("Creating task with entities:", entities)
#         task = AssistantTask.objects.create(
#             user=self.user,
#             input_text=entities.get("input_text"),
#             task_type=entities.get("action") or "New Task",
#             output_text=entities.get("task_title"),
#             due_datetime=entities.get("due_datetime"),
#             context=entities.get("context"),
#         )
#         return f"✅ Task '{task.task_type}' created." if task else "❌ Failed to create task."

#     def handle_read_email(self, entities):
#         email = self.email_service.read_email(
#             sender=entities.get("sender"),
#             query_text=entities.get("query_text"),
#         )
#         return email or "Email not found."

#     def handle_send_email(self, entities):
#         success = self.email_service.send_email(
#             receiver_name=entities.get("receiver_name"),
#             receiver_email=entities.get("receiver_email"),
#             subject=entities.get("subject"),
#             body=entities.get("body"),
#         )
#         return "✅ Email sent successfully." if success else "❌ Failed to send email."

#     def handle_reply_email(self, entities):
#         success = self.email_service.reply_to_email(
#             email_id=entities.get("email_id"),
#             body=entities.get("body"),
#         )
#         return "💬 Reply sent successfully." if success else "❌ Failed to send reply."

#     def handle_summarize_email(self, entities):
#         summary = self.email_service.summarize_email(
#             sender=entities.get("sender"),
#             query_text=entities.get("query_text"),
#         )
#         return f"🧠 Summary: {summary}" if summary else "Couldn't summarize this email."



# assistant/intent_router.py
from unified.services import MessageService
from .llm_service import LLMService
from django.conf import settings
from assistant.models import AssistantTask

APIKEY = settings.GEMINI_API_KEY


class IntentRouter:
    """
    Routes natural language user inputs to the correct handler.
    Detects user intent (e.g., summarize, find, send, task creation)
    and executes it through unified services.
    """

    def __init__(self, user=None):
        self.user = user
        self.llm_service = LLMService(user, APIKEY)
        self.message_service = MessageService(user)
        self.handlers = self._register_handlers()

    # ---------------- REGISTER HANDLERS ---------------- #
    def _register_handlers(self):
        return {
            "read_message": self.handle_read_message,
            "find_message": self.handle_find_messages,
            "send_message": self.handle_send_message,
            "reply_message": self.handle_reply_message,
            "summarize_message": self.handle_summarize_message,
            "create_task": self.handle_create_task,
            "set_reminder": self.handle_create_task,
        }

    # ---------------- MAIN ENTRY ---------------- #
    def route(self, message, context=None):
        """
        Entry point:
        1️⃣ Uses LLM to detect intent and extract entities.
        2️⃣ Detects communication channel.
        3️⃣ Routes to correct handler.
        """
        intent, entities = self._detect_intent(message, context)
        channel = entities.get("channel") or self._detect_channel(message)

        handler = self.get_handler(intent)
        if not handler:
            return f"🤔 Sorry, I couldn’t understand that request."

        try:
            return handler(entities, channel)
        except Exception as e:
            print(f"[IntentRouter] Error handling '{intent}': {e}")
            return f"❌ Something went wrong while processing '{intent}'."

    # ---------------- INTENT DETECTION ---------------- #
    def _detect_intent(self, message, context=None):
        """
        Uses LLM to infer intent & entities from natural language.
        Example: "Summarize my last 3 emails" -> summarize_message
                 "Remind me to call Alex tomorrow" -> create_task
        """
        parsed = self.llm_service.parse_intent_and_entities(message, context)
        intent = parsed.get("intent", "unknown")
        entities = parsed.get("entities", {})
        return intent, entities

    def _detect_channel(self, message: str):
        """Basic heuristic for guessing communication channel."""
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
        print(f"Finding messages in channel: {channel}")
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
        print(f"Reading message from channel: {channel}")
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
        """Summarizes a message or a group of messages."""
        service = self._get_service(channel)
        if not service:
            return "⚠️ No matching channel found."

        summary = service.summarize_message(
            sender=entities.get("sender"),
            query_text=entities.get("query_text"),
        )
        return f"🧠 Summary:\n{summary}" if summary else "Couldn't summarize this message."

    def handle_create_task(self, entities, channel="all"):
        """Creates a reminder or task."""
        print("Creating task:", entities)
        task = AssistantTask.objects.create(
            user=self.user,
            input_text=entities.get("query_text"),
            task_type=entities.get("task_type") or "Task",
            output_text=entities.get("task_title"),
            due_datetime=entities.get("due_datetime"),
            context=entities.get("context"),
        )
        return f"✅ Task '{task.task_type}' created successfully." if task else "❌ Failed to create task."

    # ---------------- SERVICE RESOLVER ---------------- #
    def _get_service(self, channel):
        return self.message_service
