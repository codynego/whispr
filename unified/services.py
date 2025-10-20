from django.utils import timezone
from datetime import timedelta
from whisprai.ai.retriever import retrieve_relevant_messages
from unified.models import ChannelAccount, Message, Conversation

class MessageService:
    """
    Service for managing user messages (emails, WhatsApp, Slack, Telegram, etc.)
    Handles all data and AI-related operations.
    """

    def __init__(self, user=None):
        self.user = user

    # ---------------- FIND MESSAGES ---------------- #
    def find_messages(self, sender=None, subject=None, date=None, query_text=None, channel=None, top_k=5):
        """
        Find messages using filters and semantic relevance.
        """
        messages = Message.objects.filter(account__user=self.user)

        if channel:
            messages = messages.filter(channel=channel)
        if sender:
            messages = messages.filter(sender__icontains=sender)
        if subject:
            messages = messages.filter(metadata__subject__icontains=subject)
        if date:
            messages = messages.filter(sent_at__date__gte=date)

        # Semantic filtering (vector search)
        if query_text:
            messages = retrieve_relevant_messages(self.user, messages, query_text, top_k=top_k)

        return {
            "count": len(messages),
            "messages": [
                {
                    "id": m.id,
                    "channel": m.channel,
                    "sender": m.sender,
                    "sender_name": m.sender_name,
                    "recipients": m.recipients,
                    "subject": m.metadata.get("subject"),
                    "content": m.content,
                    "sent_at": m.sent_at,
                    "is_read": m.is_read,
                }
                for m in messages
            ],
        }

    # ---------------- READ MESSAGE ---------------- #
    def read_message(self, sender=None, subject=None, date=None, query_text=None, channel=None):
        """
        Retrieve the most relevant or recent message from a channel.
        """
        messages = Message.objects.filter(account__user=self.user)

        if channel:
            messages = messages.filter(channel=channel)
        if sender:
            messages = messages.filter(sender__icontains=sender)
        if subject:
            messages = messages.filter(metadata__subject__icontains=subject)

        if date:
            date = date.lower()
            if date == "today":
                messages = messages.filter(sent_at__date=timezone.now().date())
            elif date == "yesterday":
                messages = messages.filter(sent_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last_week":
                start = timezone.now().date() - timedelta(days=7)
                messages = messages.filter(sent_at__date__gte=start)

        if query_text:
            messages = retrieve_relevant_messages(self.user, messages, query_text, top_k=1)

        if not messages.exists():
            return {"error": "No messages found."}

        message = messages[0] if isinstance(messages, list) else messages.first()

        return {
            "id": message.id,
            "channel": message.channel,
            "sender": message.sender,
            "sender_name": message.sender_name,
            "recipients": message.recipients,
            "subject": message.metadata.get("subject"),
            "content": message.content,
            "sent_at": message.sent_at,
            "is_read": message.is_read,
        }

    # ---------------- SUMMARIZE MESSAGE ---------------- #
    def summarize_message(self, sender=None, subject=None, date=None, query_text=None, channel=None):
        """
        Summarizes the most relevant message based on sender or query.
        """
        messages = Message.objects.filter(account__user=self.user)
        if channel:
            messages = messages.filter(channel=channel)
        if sender:
            messages = messages.filter(sender__icontains=sender)
        if subject:
            messages = messages.filter(metadata__subject__icontains=subject)

        if date:
            date = date.lower()
            if date == "today":
                messages = messages.filter(sent_at__date=timezone.now().date())
            elif date == "yesterday":
                messages = messages.filter(sent_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last_week":
                start = timezone.now().date() - timedelta(days=7)
                messages = messages.filter(sent_at__date__gte=start)

        if query_text:
            messages = retrieve_relevant_messages(self.user, messages, query_text, top_k=1)

        if not messages:
            return {"error": "No messages found for your query."}

        message = messages[0]
        body = message.content or ""
        summary = body[:200] + "..." if len(body) > 200 else body

        return {
            "message_id": message.id,
            "sender": message.sender,
            "channel": message.channel,
            "subject": message.metadata.get("subject"),
            "summary": summary,
        }

    # ---------------- SEND MESSAGE (Optional placeholder) ---------------- #
    def send_message(self, to, content, subject=None, channel="email"):
        """
        Send or reply depending on channel integration.
        """
        account = ChannelAccount.objects.filter(user=self.user, channel=channel, is_active=True).first()
        if not account:
            return {"error": f"No connected {channel} account found."}

        # TODO: Add per-channel send logic (e.g., Gmail API, WhatsApp API)
        print(f"📤 Sending via {channel} → {to}: {content}")
        return {"status": "sent", "to": to, "content": content, "channel": channel}
