from django.utils import timezone
from datetime import timedelta
from whisprai.ai.retriever import retrieve_relevant_messages
from unified.models import ChannelAccount, Message, Conversation
from unified.utils.email_util import send_gmail_email

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
        print("find_messages called with:", sender, subject, date, query_text, channel, top_k)

        if channel:
            messages = messages.filter(channel=channel)
        if sender:
            messages = messages.filter(sender__icontains=sender)
        if subject:
            messages = messages.filter(metadata__subject__icontains=subject)
        if date:
            messages = messages.filter(sent_at__date__gte=date)
            print("message after date filter", messages.count())

        print("message before retriever", messages.count())
        # Semantic filtering (vector search)
        # if query_text:
        #     messages = retrieve_relevant_messages(self.user, messages, query_text, top_k=top_k)
        print("🔎 Found", messages.count(), "messages after filters.")
        
        if messages.count() == 0:
            return {"error": "No messages found."}
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
        print("read_message called with:", sender, subject, date, query_text, channel)
        messages = Message.objects.filter(account__user=self.user)
        print("initial message count", messages.count())

        if channel:
            messages = messages.filter(channel=channel)
        if sender:
            messages = messages.filter(sender__icontains=sender)
        if subject:
            messages = messages.filter(metadata__subject__icontains=subject)

        print("message after filters", messages.count())

        if date:
            date = date.lower()
            if date == "today":
                messages = messages.filter(sent_at__date=timezone.now().date())
            elif date == "yesterday":
                messages = messages.filter(sent_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last_week":
                start = timezone.now().date() - timedelta(days=7)
                messages = messages.filter(sent_at__date__gte=start)
        print("message after date filter", messages.count())

        print("message before retriever", messages.count())

        # if query_text:
        #     messages = retrieve_relevant_messages(self.user, messages, query_text, top_k=1)
        
        print(f"🔎 Found {len(messages)} relevant messages for query.", type(messages))

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
    def summarize_message(self, sender=None, subject=None, date=None, query_text=None, channel=None, limit=5):
            """
            Summarizes multiple relevant messages (default: top 5) based on filters.
            """
            print("summarize_message called with:", sender, subject, date, query_text, channel, limit)
            messages = Message.objects.filter(account__user=self.user)

            if channel:
                messages = messages.filter(channel=channel)
            if sender:
                messages = messages.filter(sender__icontains=sender)
            if subject:
                messages = messages.filter(metadata__subject__icontains=subject)

            # 🗓 Filter by timeframe
            if date:
                date = date.lower()
                if date == "today":
                    messages = messages.filter(sent_at__date=timezone.now().date())
                elif date == "yesterday":
                    messages = messages.filter(sent_at__date=timezone.now().date() - timedelta(days=1))
                elif date == "last_week":
                    start = timezone.now().date() - timedelta(days=7)
                    messages = messages.filter(sent_at__date__gte=start)

            # 🔍 Use semantic search for relevance if query_text is provided
            # if query_text:
            #     messages = retrieve_relevant_messages(self.user, messages, query_text, top_k=limit)
            # else:
            #     messages = messages.order_by("-sent_at")[:limit]

            if len(messages) == 0:
                return {"error": "No messages found for your query."}

            summaries = []
            for msg in messages:
                body = msg.content or ""
                summary = body[:200] + "..." if len(body) > 200 else body

                summaries.append({
                    "message_id": msg.id,
                    "sender": msg.sender,
                    "subject": msg.metadata.get("subject") if msg.metadata else None,
                    "channel": msg.channel,
                    "date": msg.sent_at,
                    "summary": summary,
                })

            combined_summary = "\n\n".join(
                [f"• {s['sender']}: {s['summary']}" for s in summaries]
            )

            return {
                "total_messages": len(summaries),
                "channel": channel or "all",
                "summaries": summaries,
                "combined_summary": combined_summary
            }

    # ---------------- SEND MESSAGE (Optional placeholder) ---------------- #
    def send_message(self, receiver_name, receiver, body, subject=None, channel="email"):
        """
        Send or reply depending on channel integration.
        """
        print("send_message called with:", receiver_name, receiver, body, subject, channel)
        account = ChannelAccount.objects.filter(user=self.user, channel=channel, is_active=True).first()
        print("Found account:", account)
        if not account:
            print("No connected account found for channel:", channel)
            return {"error": f"No connected {channel} account found."}


        # --- 2️⃣ Send email via Gmail API ---

        to_email = receiver
        success = send_gmail_email(
            account,
            to_email=to_email,
            subject=subject,
            body=body
        )
        

        print(f"Sending email to {receiver_name} <{receiver}>")
        return True

        # TODO: Add per-channel send logic (e.g., Gmail API, WhatsApp API)
        print(f"📤 Sending via {channel} → {to}: {content}")
        return {"status": "sent", "to": to, "content": content, "channel": channel}
