from emails.models import Email
from django.utils import timezone
from datetime import timedelta


class EmailService:
    """
    Service for managing user emails.
    Handles all database and functional operations related to user emails.
    Used by the IntentRouter.

    """

    def __init__(self, user=None):
        self.user = user 

    # ---------------- FIND EMAIL ---------------- #
    def find_emails(self, sender=None, subject=None, date=None, limit=5):
        """
        Searches user emails based on given filters.
        """
        qs = Email.objects.all()

        if self.user:
            qs = qs.filter(account__user=self.user)

        if sender:
            qs = qs.filter(sender__icontains=sender)
        if subject:
            qs = qs.filter(subject__icontains=subject)

        # Date filtering
        if date:
            date = date.lower()
            if date == "today":
                qs = qs.filter(received_at__date=timezone.now().date())
            elif date == "yesterday":
                qs = qs.filter(received_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last_week":
                start = timezone.now().date() - timedelta(days=7)
                qs = qs.filter(received_at__date__gte=start)

        emails = list(
            qs.order_by("-received_at")[:limit].values(
                "id", "sender", "subject", "body", "received_at"
            )
        )
        return emails

    # ---------------- READ EMAIL ---------------- #
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
        Sends an email (placeholder logic for now).
        """
        print(f"Sending email to {recipient} — Subject: {subject}\nBody: {body}")
        return True

    # ---------------- REPLY EMAIL ---------------- #
    def reply_to_email(self, sender, body):
        """
        Replies to the latest email thread from a sender.
        If no sender is given, returns an error.
        """
        if not sender:
            return {"error": "No sender provided for reply."}

        qs = Email.objects.all()
        if self.user:
            qs = qs.filter(account__user=self.user)

        latest_email = qs.filter(sender__icontains=sender).order_by("-received_at").first()
        if not latest_email:
            return {"error": f"No recent email thread found for {sender}."}

        print(f"Replying to {latest_email.sender}: {body}")
        # (In real use: send reply via API, link thread_id, etc.)
        return {
            "status": "success",
            "replied_to": latest_email.id,
            "recipient": latest_email.sender,
            "subject": f"Re: {latest_email.subject}",
        }

    # ---------------- SUMMARIZE EMAIL ---------------- #
    def summarize_email(self, sender=None):
        """
        Summarizes the latest email thread from a sender.
        """
        if not sender:
            return {"error": "No sender provided for summary."}

        qs = Email.objects.all()
        if self.user:
            qs = qs.filter(account__user=self.user)

        latest_email = qs.filter(sender__icontains=sender).order_by("-received_at").first()
        if not latest_email:
            return {"error": f"No recent email thread found for {sender}."}

        body = latest_email.body or ""
        # summary = body[:100] + "..." if len(body) > 100 else body
        summary = body

        return {
            "email_id": latest_email.id,
            "sender": latest_email.sender,
            "subject": latest_email.subject,
            "summary": summary,
        }
