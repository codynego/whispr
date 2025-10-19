# email_views.py
from rest_framework import generics, permissions, status, filters
from unified.models import ChannelAccount, Message, UserRule
from unified.serializers import ChannelAccountSerializer, MessageSerializer, MessageSyncSerializer, UserRuleSerializer
from unified.tasks.common_tasks import sync_channel_account
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.http import JsonResponse
from unified.models import Conversation
from unified.serializers import ConversationSerializer




# --- Pagination ---
class MessagePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

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

# --- Messages / Conversations ---
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
        if not instance.is_read:
            instance.is_read = True
            instance.save(update_fields=["is_read"])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def sync_messages(request):
    """
    Trigger message sync for the authenticated user's channel accounts.
    """
    serializer = MessageSyncSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    account_id = serializer.validated_data['account_id']

    try:
        account = ChannelAccount.objects.get(user=request.user, id=account_id, is_active=True)
    except ChannelAccount.DoesNotExist:
        return Response({"error": "No active account found for user."}, status=status.HTTP_400_BAD_REQUEST)

    # Trigger async Celery task
    task = sync_channel_account.delay(account.id)

    return Response({"message": "Sync started successfully", "task_id": task.id}, status=status.HTTP_202_ACCEPTED)




class ConversationListView(generics.ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        channel = self.request.query_params.get("channel")
        queryset = Conversation.objects.filter(account__user=user)
        if channel:
            queryset = queryset.filter(channel=channel)
        return queryset.order_by("-last_message_at")


class ConversationDetailView(generics.RetrieveAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(account__user=self.request.user)




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


class DeactivateChannelAccountView(generics.UpdateAPIView):
    serializer_class = ChannelAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = ChannelAccount.objects.all()

    def patch(self, request, *args, **kwargs):
        account = self.get_object()
        if account.user != request.user:
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        account.is_active = False
        account.save(update_fields=["is_active"])
        return Response({"detail": f"Account '{account.address_or_id}' deactivated."}, status=status.HTTP_200_OK)
