from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from unified.models import (
    ChannelAccount,
    Message,
    UserRule,
    Conversation,
)
from unified.serializers import (
    ChannelAccountSerializer,
    MessageSerializer,
    MessageSyncSerializer,
    UserRuleSerializer,
    ConversationSerializer,
    ConversationWithMessagesSerializer,
)
from unified.tasks.common_tasks import sync_channel_account
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q, Count

from assistant.models import AssistantTask
from django.shortcuts import get_object_or_404
from unified.serializers import MessageSendSerializer
from unified.utils.email_util import send_gmail_email




# --- Pagination Classes ---
class MessagePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ConversationPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "total_items": self.page.paginator.count,
            "total_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })


# --- Channel Accounts ---
class ChannelAccountListView(generics.ListAPIView):
    serializer_class = ChannelAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChannelAccount.objects.filter(user=self.request.user)


class ChannelAccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ChannelAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChannelAccount.objects.filter(user=self.request.user)


# --- Messages ---
class MessageListView(generics.ListAPIView):
    """
    List all messages for the authenticated user with filtering and pagination.
    Filters:
      - ?account=<account_id>
      - ?channel=email|whatsapp|slack
      - ?importance=high|medium|low
      - ?is_read=true|false
    """
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = MessagePagination

    def get_queryset(self):
        user = self.request.user
        queryset = Message.objects.filter(account__user=user)

        account_id = self.request.query_params.get("account")
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        channel = self.request.query_params.get("channel")
        if channel:
            queryset = queryset.filter(channel__iexact=channel)

        importance = self.request.query_params.get("importance")
        if importance:
            queryset = queryset.filter(importance__iexact=importance)

        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == "true")

        queryset = queryset.order_by("-sent_at")
        return queryset


class MessageDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(account__user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Mark message as read when retrieved
        if not instance.is_read:
            instance.is_read = True
            instance.save(update_fields=["is_read"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# --- Message Sync ---
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def sync_messages(request):
    """
    Trigger message sync for the authenticated user's channel accounts.
    """
    serializer = MessageSyncSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    account_id = serializer.validated_data["account_id"]

    try:
        account = ChannelAccount.objects.get(
            user=request.user, id=account_id, is_active=True
        )
    except ChannelAccount.DoesNotExist:
        return Response(
            {"error": "No active account found for user."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Trigger async Celery task
    task = sync_channel_account.delay(account.id)

    return Response(
        {"message": "Sync started successfully"},
        status=status.HTTP_202_ACCEPTED,
    )


# --- Conversations ---
class ConversationListView(generics.ListAPIView):
    """
    Paginated list of conversations for the authenticated user.
    Filters:
      - ?channel=email|whatsapp|slack
      - ?account=<account_id>
      - ?search=keyword (matches title, participants, or last message)
    """
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConversationPagination

    def get_queryset(self):
        user = self.request.user
        queryset = Conversation.objects.filter(account__user=user)

        channel = self.request.query_params.get("channel")
        if channel:
            queryset = queryset.filter(channel__iexact=channel)

        account_id = self.request.query_params.get("account")
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                title__icontains=search
            ) | queryset.filter(participants__icontains=search)

        return queryset.order_by("-last_message_at")


class ConversationDetailView(generics.RetrieveAPIView):
    """
    Retrieve a single conversation with its messages.
    """
    serializer_class = ConversationWithMessagesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(account__user=self.request.user)


# --- User Rules ---
class UserMessageRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = UserRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserRule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserMessageRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserRule.objects.filter(user=self.request.user)


# --- Deactivate Channel ---
class DeactivateChannelAccountView(generics.UpdateAPIView):
    serializer_class = ChannelAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ChannelAccount.objects.all()

    def patch(self, request, *args, **kwargs):
        account = self.get_object()
        if account.user != request.user:
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        account.is_active = False
        account.save(update_fields=["is_active"])
        return Response(
            {"detail": f"Account '{account.address_or_id}' deactivated."},
            status=status.HTTP_200_OK,
        )




class DashboardOverviewAPIView(APIView):
    """
    Unified dashboard API for Whisone — aggregates messages, conversations,
    and assistant task activity across all connected channels.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        # --- CHANNEL ACCOUNTS ---
        connected_accounts = ChannelAccount.objects.filter(user=user, is_active=True)
        total_channels = connected_accounts.count()

        # --- MESSAGES ---
        messages_today = Message.objects.filter(
            account__user=user,
            created_at__date=today,
        )
        total_messages = messages_today.count()
        unread_messages = messages_today.filter(is_read=False).count()
        important_messages = messages_today.filter(
            importance__in=["high", "critical"]
        ).count()

        # --- CONVERSATIONS ---
        active_conversations = (
            Conversation.objects.filter(account__user=user, is_archived=False)
            .annotate(total_msgs=Count("messages"))
            .order_by("-last_message_at")[:5]
        )

        # --- AI TASKS ---
        tasks_qs = AssistantTask.objects.filter(user=user).order_by("-created_at")[:5]
        ai_tasks = [
            {
                "id": t.id,
                "task_type": t.task_type,
                "status": t.status,
                "input_text": t.input_text[:120] + ("..." if len(t.input_text) > 120 else ""),
                "due_datetime": t.due_datetime,
                "is_completed": t.is_completed,
                "created_at": t.created_at,
            }
            for t in tasks_qs
        ]

        # --- PERFORMANCE METRICS (sample logic) ---
        performance = {
            "ai_tasks_completed": AssistantTask.objects.filter(
                user=user, status="completed"
            ).count(),
            "important_threads": important_messages,
            "missed_messages": unread_messages,
            "connected_channels": total_channels,
            "trend": "+9%",  # placeholder, could later be computed dynamically
        }

        # --- AI SUMMARY ---
        ai_summary = {
            "greeting": f"Good {self.get_time_of_day()}, {user.first_name or 'there'} 👋",
            "summary_text": (
                f"You’ve received {total_messages} messages today across {total_channels} channels. "
                f"{unread_messages} are still unread, and {important_messages} are important."
            ),
            "suggestions": [
                "Reply to important messages",
                "Review unread conversations",
                "Check your recent AI tasks",
            ],
        }

        # --- DATA STRUCTURE ---
        data = {
            "summary": ai_summary,
            "stats": {
                "total_channels": total_channels,
                "total_messages": total_messages,
                "unread_messages": unread_messages,
                "important_messages": important_messages,
                "channel_breakdown": self.get_channel_breakdown(user),
            },
            "active_conversations": [
                {
                    "id": c.id,
                    "title": c.title or "(No Title)",
                    "channel": c.channel,
                    "last_message_at": c.last_message_at,
                    "message_count": c.total_msgs,
                }
                for c in active_conversations
            ],
            "tasks": ai_tasks,
            "performance": performance,
        }

        return Response(data)

    def get_time_of_day(self):
        """Return current time of day label."""
        hour = timezone.now().hour
        if hour < 12:
            return "morning"
        elif hour < 18:
            return "afternoon"
        return "evening"

    def get_channel_breakdown(self, user):
        """Return per-channel message count for user."""
        channels = (
            Message.objects.filter(account__user=user)
            .values("channel")
            .annotate(total=Count("id"))
        )
        return {c["channel"]: c["total"] for c in channels}



# unified/views/send_message.py

# (later you can import send_whatsapp_message, send_slack_message, etc.)

class SendMessageView(generics.GenericAPIView):
    serializer_class = MessageSendSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        print("Reached SendMessageView")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        print("Validated data:", data)

        message_id = data.get("message_id")
        message = get_object_or_404(Message, id=message_id, account__user=request.user)

        # Get linked account
        account = message.account
        if not account:
            return Response({"error": "No account linked to this message."}, status=400)

        channel = account.channel  # e.g., "email", "whatsapp"
        provider = account.provider  # e.g., "gmail", "outlook", "meta"

        result = None
        print("Preparing to send message via", channel, provider)

        try:
            if channel == "email":
                if provider == "gmail":
                    print("Sending Gmail email...")
                    result = send_gmail_email.delay(
                        account=account,
                        to_email=data.get("to") or message.to_email,
                        subject=data.get("subject") or message.subject,
                        body=data.get("body") or message.body,
                        body_html=data.get("body_html"),
                        attachments=data.get("attachments"),
                        thread_id=message.thread_id,
                    )
                    print("Gmail email sent:", result)
                elif provider == "outlook":
                    # Placeholder for Microsoft API
                    pass

            elif channel == "whatsapp":
                # call send_whatsapp_message(account, message)
                pass

            elif channel == "slack":
                # call send_slack_message(account, message)
                pass

            else:
                return Response({"error": "Unsupported channel"}, status=400)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

        if result:
            return Response({"status": "sent", "data": result}, status=200)
        return Response({"status": "failed"}, status=500)
