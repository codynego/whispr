from datetime import timedelta
from django.utils import timezone
from whisprai.ai.retriever import retrieve_relevant_messages
from messages.models import Message, Conversation, ChannelAccount
from emails.utils import send_gmail_email
from emails.models import EmailAccount  # still used for Gmail send fallback


class MessageService:
    """
    Unified Message Service
    ---------------------------------
    Handles finding, reading, summarizing, sending, and replying
    across all supported communication channels.
    """

    def __init__(self, user=None, channel=None):
        self.user = user
        self.channel = channel  # optional: email, whatsapp, slack, etc.


    # ---------------- FIND MESSAGES ---------------- #
    def find_messages(self, sender=None, subject=None, date=None, query_text=None, top_k=5):
        """
        Find messages by sender, subject, date, or semantic query.
        """
        qs = Message.objects.filter(account__user=self.user)
        if self.channel:
            qs = qs.filter(channel=self.channel)

        if sender:
            qs = qs.filter(sender_address__icontains=sender)
        if subject:
            qs = qs.filter(subject__icontains=subject)
        if date:
            qs = qs.filter(sent_at__date__gte=date)

        if query_text:
            relevant = retrieve_relevant_messages(self.user, qs, query_text, top_k=top_k)
        else:
            relevant = qs.order_by("-sent_at")[:top_k]

        return {
            "count": len(relevant),
            "messages": [
                {
                    "id": msg.id,
                    "sender_name": msg.sender_name,
                    "sender_address": msg.sender_address,
                    "recipient_address": msg.recipient_address,
                    "subject": msg.subject,
                    "body": msg.body,
                    "sent_at": msg.sent_at,
                    "channel": msg.channel,
                    "importance": msg.importance,
                }
                for msg in relevant
            ],
        }


    # ---------------- READ MESSAGE / THREAD ---------------- #
    def read_message(self, sender=None, subject=None, date=None, query_text=None):
        """
        Retrieves the most relevant message or thread from a sender.
        """
        if not sender and not query_text:
            return {"error": "Either sender or query_text must be provided."}

        qs = Message.objects.filter(account__user=self.user)
        if self.channel:
            qs = qs.filter(channel=self.channel)

        if sender:
            qs = qs.filter(sender_address__icontains=sender)
        if subject:
            qs = qs.filter(subject__icontains=subject)

        if date:
            date = date.lower()
            if date == "today":
                qs = qs.filter(sent_at__date=timezone.now().date())
            elif date == "yesterday":
                qs = qs.filter(sent_at__date=timezone.now().date() - timedelta(days=1))
            elif date == "last_week":
                start = timezone.now().date() - timedelta(days=7)
                qs = qs.filter(sent_at__date__gte=start)

        # Semantic search
        if query_text:
            relevant = retrieve_relevant_messages(self.user, qs, query_text, top_k=1)
            if not relevant:
                return {"error": "No relevant messages found."}
            message = relevant[0]
        else:
            message = qs.order_by("-sent_at").first()
            if not message:
                return {"error": "No messages found."}

        # Attach thread
        conversation = message.conversation
        thread = conversation.messages.order_by("sent_at") if conversation else [message]

        return {
            "conversation_id": conversation.id if conversation else None,
            "topic": getattr(conversation, "topic", message.subject),
            "messages": [
                {
                    "id": m.id,
                    "sender_name": m.sender_name,
                    "sender_address": m.sender_address,
                    "recipient_address": m.recipient_address,
                    "subject": m.subject,
                    "body": m.body,
                    "sent_at": m.sent_at,
                    "channel": m.channel,
                }
                for m in thread
            ],
        }


    # ---------------- SUMMARIZE MESSAGE ---------------- #
    def summarize_message(self, sender=None, subject=None, date=None, query_text=None):
        """
        Summarizes the most relevant message.
        """
        result = self.read_message(sender, subject, date, query_text)
        if "error" in result:
            return result

        # Use first message body for now
        msg = result["messages"][-1]
        body = msg.get("body", "")
        summary = body[:200] + "..." if len(body) > 200 else body

        return {
            "conversation_id": result.get("conversation_id"),
            "subject": msg.get("subject"),
            "summary": summary,
            "channel": msg.get("channel"),
        }


    # ---------------- SEND MESSAGE ---------------- #
    def send_message(self, receiver_name, receiver_address, subject, body):
        """
        Sends a message across channels.
        Currently only supports email sending via Gmail.
        """
        if not self.channel:
            return {"error": "Channel must be specified to send a message."}

        if self.channel == "email":
            # Get user's active email account
            account = EmailAccount.objects.filter(user=self.user, is_active=True).first()
            if not account:
                return {"error": "No connected email account found."}

            success = send_gmail_email(
                account,
                to_email=receiver_address,
                subject=subject,
                body=body,
            )
            if not success:
                return {"error": "Failed to send email."}

            # Attach or create conversation
            conversation, _ = Conversation.objects.get_or_create(
                account=account,
                topic=f"Email with {receiver_name}",
                channel="email",
            )

            Message.objects.create(
                account=account,
                conversation=conversation,
                sender_address=account.address_or_id,
                recipient_address=receiver_address,
                subject=subject,
                body=body,
                channel="email",
                sent_at=timezone.now(),
            )

            return {"status": "sent", "channel": "email", "to": receiver_address}

        # Future: WhatsApp, Slack, etc.
        return {"error": f"Sending not yet supported for channel: {self.channel}"}


    # ---------------- REPLY MESSAGE ---------------- #
    def reply_message(self, sender=None, body=None):
        """
        Reply to the latest message thread with a sender.
        """
        if not sender:
            return {"error": "No sender specified."}

        qs = Message.objects.filter(account__user=self.user)
        if self.channel:
            qs = qs.filter(channel=self.channel)

        latest = qs.filter(sender_address__icontains=sender).order_by("-sent_at").first()
        if not latest:
            return {"error": f"No recent messages found for {sender}."}

        conversation = latest.conversation
        if not conversation:
            return {"error": "No conversation thread found."}

        # For email replies
        if latest.channel == "email":
            account = EmailAccount.objects.filter(user=self.user, is_active=True).first()
            if not account:
                return {"error": "No connected email account found."}

            subject = f"Re: {latest.subject}" if latest.subject else "Re:"
            success = send_gmail_email(
                account,
                to_email=latest.sender_address,
                subject=subject,
                body=body,
            )
            if not success:
                return {"error": "Failed to send reply."}

        # Create local message record
        Message.objects.create(
            account=latest.account,
            conversation=conversation,
            sender_address=latest.recipient_address,
            recipient_address=latest.sender_address,
            subject=f"Re: {latest.subject}",
            body=body,
            channel=latest.channel,
            sent_at=timezone.now(),
        )

        return {
            "status": "replied",
            "conversation_id": conversation.id,
            "recipient": latest.sender_address,
            "subject": f"Re: {latest.subject}",
        }
