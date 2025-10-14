from emails.models import Email
from django.utils import timezone
from datetime import timedelta
from whisprai.ai.retriever import retrieve_relevant_emails

class EmailService:
    """
    Service for managing user emails.
    Handles all database and functional operations related to user emails.
    Used by the IntentRouter.

    """

    def __init__(self, user=None):
        self.user = user 


    def find_emails(self, sender=None, subject=None, date=None, query_text=None, top_k=5):
        # 1️⃣ First, try DB filters
        emails = Email.objects.filter(account__user=self.user)
        if sender:
            emails = emails.filter(sender__icontains=sender)
        if subject:
            emails = emails.filter(subject__icontains=subject)
        if date:
            date = date.lower()
            if date == "today":
                emails = emails.filter(received_at__date=timezone.now().date())
            elif date == "yesterday":
                emails = emails.filter(received_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last_week":
                start = timezone.now().date() - timedelta(days=7)
                emails = emails.filter(received_at__date__gte=start)

        if query_text:
            semantic_emails = retrieve_relevant_emails(self.user, emails, query_text, top_k=top_k)
            email_list = semantic_emails

        return {
            "count": len(email_list),
            "emails": [
                {
                    "id": email.id,
                    "sender": email.sender,
                    "sender_name": getattr(email, "sender_name", None),
                    "recipient": email.recipient,
                    "subject": email.subject,
                    "body": email.body,
                    "received_at": email.received_at,
                    "is_read": getattr(email, "is_read", False),
                }
                for email in email_list
            ]
        }


    def read_email(self, sender=None, subject=None, date=None, query_text=None,):
        """
        Retrieves the most relevant email from a sender or based on a query.
        """
        if not sender and not query_text:
            return {"error": "Either sender or query_text must be provided."}
        emails = Email.objects.filter(account__user=self.user)
        if sender:
            emails = emails.filter(sender__icontains=sender)
        if subject:
            emails = emails.filter(subject__icontains=subject)
        if date:
            date = date.lower()
            if date == "today":
                emails = emails.filter(received_at__date=timezone.now().date())
            elif date == "yesterday":
                emails = emails.filter(received_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last_week":
                start = timezone.now().date() - timedelta(days=7)
                emails = emails.filter(received_at__date__gte=start)

        # Use embeddings if query_text is provided
        if query_text:
            relevant_emails = retrieve_relevant_emails(self.user, emails, query_text, top_k=1)
            if not relevant_emails:
                return {"error": "No relevant emails found for your query."}
            email = relevant_emails
        # else:
        #     email = emails.first()
        #     if not email:
        #         return {"error": "No emails found."}

        return {
                "count": len(emails),
                "emails": [
                    {
                        "id": email.id,
                        "sender": email.sender,
                        "sender_name": getattr(email, "sender_name", None),
                        "recipient": email.recipient,
                        "subject": email.subject,
                        "body": email.body,
                        "received_at": email.received_at,
                        "is_read": getattr(email, "is_read", False),
                    }
                    for email in emails
                ]
            }

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


    def summarize_email(self, sender=None, subject=None, date=None, query_text=None):
        """
        Summarizes the most relevant email based on sender or query.
        """
        if not sender and not query_text:
            return {"error": "Provide either sender or query_text for summary."}

        emails = Email.objects.filter(account__user=self.user)
        if sender:
            emails = emails.filter(sender__icontains=sender)
        if subject:
            emails = emails.filter(subject__icontains=subject)
        if date:
            date = date.lower()
            if date == "today":
                emails = emails.filter(received_at__date=timezone.now().date())
            elif date == "yesterday":
                emails = emails.filter(received_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last_week":
                start = timezone.now().date() - timedelta(days=7)
                emails = emails.filter(received_at__date__gte=start)


        # Use embeddings to find the most relevant email
        if query_text:
            relevant_emails = retrieve_relevant_emails(self.user, emails, query_text, top_k=1)
            if not relevant_emails:
                return {"error": "No relevant emails found for your query."}
            email = relevant_emails[0]


        body = email.body or ""
        # Optionally integrate an LLM summarizer here
        summary = body[:200] + "..." if len(body) > 200 else body

        return {
            "email_id": email.id,
            "sender": email.sender,
            "subject": email.subject,
            "body": body,
            "summary": summary,
        }
