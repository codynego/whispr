from emails.services import EmailService
from .llm_service import LLMService
from django.conf import settings

APIKEY = settings.GEMINI_API_KEY


class IntentRouter:
    """
    Routes user intents or @commands to the appropriate handler.
    Supports both LLM-inferred intents and explicit @commands.
    """

    def __init__(self, user=None):
        self.user = user
        self.llm_service = LLMService(self.user, APIKEY)
        self.email_service = EmailService(user=user)
        self.handlers = self._register_handlers()
        self.command_map = {
            "@read": "read_message",
            "@find": "find_email",
            "@send": "send_email",
            "@reply": "reply_email",
            "@summarize": "summarize_email",
        }

    # ---------------- REGISTER HANDLERS ---------------- #
    def _register_handlers(self):
        return {
            "get_content": self.handle_read_email,
            "read_message": self.handle_read_email,
            "find_email": self.handle_find_emails,
            "find_emails": self.handle_find_emails,
            "send_email": self.handle_send_email,
            "reply_email": self.handle_reply_email,
            "summarize_email": self.handle_summarize_email,
        }

    # ---------------- GET HANDLER ---------------- #
    def get_handler(self, intent_name):
        return self.handlers.get(intent_name)

    # ---------------- MAIN ENTRY ---------------- #
    def route(self, message, context=None):
        """
        Main entry:
        1. Checks for explicit @commands first
        2. If none, uses LLM to infer intent
        3. Routes to matching handler
        """
        intent, entities = self._detect_intent(message, context)

        handler = self.get_handler(intent)
        if not handler:
            return f"Unknown or unsupported intent: '{intent}'"

        try:
            return handler(entities)
        except Exception as e:
            print(f"[IntentRouter] Error handling '{intent}':", e)
            return f"An error occurred while processing '{intent}'."

    # ---------------- INTENT DETECTION ---------------- #
    def _detect_intent(self, message, context=None):
        # 1️⃣ Check for explicit command (e.g. "@find mail from ALX")
        for cmd, intent in self.command_map.items():
            if cmd in message.lower():
                entities = self.llm_service.extract_entities(message, intent)
                return intent, entities

        # 2️⃣ Fall back to LLM parsing
        parsed = self.llm_service.parse_intent_and_entities(message, context)
        intent = parsed.get("intent", "unknown")
        entities = parsed.get("entities", {})
        return intent, entities

    # ---------------- HANDLER METHODS ---------------- #
    def handle_find_emails(self, entities):
        emails = self.email_service.find_emails(
            sender=entities.get("sender"),
            subject=entities.get("subject"),
            date=entities.get("date"),
            limit=entities.get("limit", 5),
        )
        return emails or "No emails found matching your query."

    def handle_read_email(self, entities):
        email = self.email_service.read_email(
            email_id=entities.get("email_id")
        )
        return email or "Email not found."

    def handle_send_email(self, entities):
        success = self.email_service.send_email(
            recipient=entities.get("recipient"),
            subject=entities.get("subject"),
            body=entities.get("body"),
        )
        return "✅ Email sent successfully." if success else "❌ Failed to send email."

    def handle_reply_email(self, entities):
        success = self.email_service.reply_to_email(
            email_id=entities.get("email_id"),
            body=entities.get("body"),
        )
        return "💬 Reply sent successfully." if success else "❌ Failed to send reply."

    def handle_summarize_email(self, entities):
        summary = self.email_service.summarize_email(
            sender=entities.get("sender")
        )
        return f"🧠 Summary: {summary}" if summary else "Couldn't summarize this email."
