from emails.models import Email
from django.utils import timezone
from datetime import timedelta

class EmailService:
    """
    Handles all database and functional operations related to user emails.
    Used by the IntentRouter.
    """

    def __init__(self, user=None):
        self.user = user  # you can pass the user from request for personalized queries

    # ---------------- FIND EMAIL ---------------- #
    def find_emails(self, sender=None, subject=None, date=None, limit=5):
        """
        Searches user emails based on given filters.
        """
        qs = Email.objects.all()

        # Optional filtering by user
        if self.user:
            qs = qs.filter(account__user=self.user)

        if sender:
            qs = qs.filter(sender__icontains=sender)
        if subject:
            qs = qs.filter(subject__icontains=subject)

        # Handle date filters
        if date:
            date = date.lower()
            if date == "today":
                qs = qs.filter(received_at__date=timezone.now().date())
            elif date == "yesterday":
                qs = qs.filter(received_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last week":
                start = timezone.now().date() - timedelta(days=7)
                qs = qs.filter(received_at__date__gte=start)

        emails = list(qs.order_by("-received_at")[:limit].values("id", "sender", "subject", "snippet", "received_at"))
        return emails

    def read_email(self, email_id):
        """
        Retrieves a specific email by ID.
        """
        try:
            email = Email.objects.get(id=email_id, account__user=self.user)
            return {
                "id": email.id,
                "sender": email.sender,
                "sender_name": email.sender_name,
                "recipient": email.recipient,
                "subject": email.subject,
                "body": email.body,
                "received_at": email.received_at,
                "is_read": email.is_read,
            }
        except Email.DoesNotExist:
            return None

    # ---------------- SEND EMAIL ---------------- #
    def send_email(self, recipient, subject, body):
        """
        Sends an email (could connect to Gmail API, SMTP, or your internal system).
        """
        # Example placeholder logic for now:
        print(f"Sending email to {recipient} — Subject: {subject}\nBody: {body}")
        return True

    # ---------------- REPLY EMAIL ---------------- #
    def reply_to_email(self, email_id, body):
        """
        Replies to a specific email.
        """
        try:
            email = Email.objects.get(id=email_id, account__user=self.user)
        except Email.DoesNotExist:
            return {"error": "Email not found"}

        print(f"Replying to {email.sender}: {body}")
        # Example placeholder for sending logic
        return True

    # ---------------- SUMMARIZE EMAIL ---------------- #
    def summarize_email(self, email_id):
        """
        Summarizes an email body (can later use Gemini API for smart summaries).
        """
        try:
            email = Email.objects.get(id=email_id, account__user=self.user)
        except Email.DoesNotExist:
            return {"error": "Email not found"}

        # Example summary logic — you’ll replace this with LLM integration later
        body = email.body or ""
        summary = body[:100] + "..." if len(body) > 100 else body
        return summary
