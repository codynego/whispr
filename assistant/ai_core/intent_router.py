from emails.services import EmailService
from .llm_service import LLMService
from django.conf import settings
APIKEY = settings.GEMINI_API_KEY

class IntentRouter:
    """
    Dynamically routes intents to appropriate handler methods
    using an internal registry.
    """

    def __init__(self, user=None):
        self.user = user
        self.llm_service = LLMService(self.user, APIKEY)
        self.email_service = EmailService(user=user)
        self.handlers = self._register_handlers()

    # ---------------- REGISTER HANDLERS ---------------- #
    def _register_handlers(self):
        """
        Register all known intents and their corresponding handler methods.
        """
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
        """
        Returns the correct handler function for a given intent.
        """
        return self.handlers.get(intent_name)

    # ---------------- MAIN ENTRY ---------------- #
    def route(self, message, context=None):
        """
        Main entry point:
        - Parse message into {intent, entities}
        - Fetch and run appropriate handler
        """
        parsed = self.llm_service.parse_intent_and_entities(message, context)
        intent = parsed.get("intent")
        entities = parsed.get("entities", {})

        if not intent:
            return "Sorry, I couldn’t understand your request."

        handler = self.get_handler(intent)
        if not handler:
            return f"Unknown intent '{intent}'."

        try:
            return handler(entities)
        except Exception as e:
            return f"Error while handling '{intent}': {e}"

    # ---------------- HANDLER METHODS ---------------- #
    def handle_find_emails(self, entities):
        emails = self.email_service.find_emails(
            sender=entities.get("sender"),
            subject=entities.get("subject"),
            date=entities.get("date"),
            limit=entities.get("limit", 5),
        )
        if not emails:
            return "No emails found matching your query."
        return emails

    def handle_read_email(self, entities):
        email = self.email_service.read_email(
            email_id=entities.get("email_id")
        )
        if not email:
            return "Email not found."
        return email

    def handle_send_email(self, entities):
        success = self.email_service.send_email(
            recipient=entities.get("recipient"),
            subject=entities.get("subject"),
            body=entities.get("body"),
        )
        return "Email sent successfully." if success else "Failed to send email."

    def handle_reply_email(self, entities):
        success = self.email_service.reply_to_email(
            email_id=entities.get("email_id"),
            body=entities.get("body"),
        )
        return "Reply sent successfully." if success else "Failed to send reply."

    def handle_summarize_email(self, entities):
        summary = self.email_service.summarize_email(
            email_id=entities.get("email_id")
        )
        return f"Summary: {summary}"
