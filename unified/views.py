# views.py
from rest_framework import generics, permissions
from rest_framework.response import Response
from emails.models import EmailAccount, Email
# from whatsapp.models import WhatsAppAccount


from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from itertools import chain
from django.core.paginator import Paginator

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from assistant.models import AssistantTask
from whatsapp.tasks import send_whatsapp_message_task


from rest_framework import generics, permissions, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.http import JsonResponse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import ChannelAccount, Conversation, Message, UserRule
from .serializers import ChannelAccountSerializer, MessageSerializer, UserRuleSerializer, MessageSyncSerializer
from unified.tasks.common_tasks import sync_channel_account

import json
import jwt




# === CONFIG ===
REDIRECT_URI = "http://localhost:3000/dashboard/settings/integrations/callbacks"
CLIENT_SECRET_FILE = "emails/credentials/client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
    'https://www.googleapis.com/auth/gmail.send'
    
]


class GmailOAuthInitView(generics.GenericAPIView):
    """Step 1: Start OAuth flow and return Google Auth URL."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, provider):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "User not authenticated"}, status=401)

        # Encode user ID into the state parameter
        state_data = {"uid": urlsafe_base64_encode(force_bytes(request.user.id))}
        state_str = json.dumps(state_data)

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state_str,
        )

        return JsonResponse({"url": auth_url})


class GmailOAuthCallbackView(generics.GenericAPIView):
    """Step 2: Handle Google's redirect and store tokens."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code = request.GET.get("code")

        if not code:
            return JsonResponse({"error": "Missing authorization code"}, status=400)

        # Decode state → user ID
        try:
            user = request.user
        except Exception as e:
            return JsonResponse({"error": f"Invalid state: {str(e)}"}, status=400)

        # Recreate the OAuth flow to fetch token
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )

        try:
            flow.fetch_token(code=code)
        except Exception as e:
            return JsonResponse({"error": f"Token exchange failed: {str(e)}"}, status=400)

        creds = flow.credentials

        # Decode ID token to extract Gmail email
        decoded_token = jwt.decode(creds.id_token, options={"verify_signature": False})
        email = decoded_token.get("email")

        if not email:
            return JsonResponse({"error": "Could not extract email from token"}, status=400)

        # Save or update Gmail account
        EmailAccount.objects.update_or_create(
            user=user,
            provider="gmail",
            email_address=email,
            defaults={
                "email_address": email,
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_expires_at": creds.expiry,
            },
        )

        return JsonResponse({
            "message": "Gmail account connected successfully!",
            "email": email
        })



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

# --- Sync messages ---


# --- User Rules ---
class UserRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = UserRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserRule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class UserRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserRule.objects.filter(user=self.request.user)

# --- Deactivate Account ---
class DeactivateChannelAccountView(generics.UpdateAPIView):
    queryset = ChannelAccount.objects.all()
    serializer_class = ChannelAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        account = self.get_object()
        if account.user != request.user:
            return Response({"detail": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        account.is_active = False
        account.save(update_fields=["is_active"])
        return Response({"detail": f"{account.address_or_id} deactivated"}, status=status.HTTP_200_OK)




class DashboardOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        # --- EMAIL STATS ---
        email_today = Email.objects.filter(account__user=user, created_at__date=today)
        total_emails = email_today.count()
        unread_emails = email_today.filter(is_read=False).count()
        important_emails = email_today.filter(importance_score__gte=0.5).count()

        # # --- WHATSAPP STATS ---
        # whatsapp_today = WhatsAppMessage.objects.filter(user=user, created_at__date=today)
        # total_whatsapp = whatsapp_today.count()
        # unread_whatsapp = whatsapp_today.filter(is_read=False).count()

        total_whatsapp = 0
        unread_whatsapp = 0

        # --- COMBINED STATS ---
        total_messages = total_emails + total_whatsapp
        unread_messages = unread_emails + unread_whatsapp


        # --- AI SUMMARY ---
        ai_summary = {
            "greeting": f"Good {self.get_time_of_day()}, {user.first_name or 'there'} 👋",
            "summary_text": (
                f"You’ve received {total_messages} messages today "
                f"({total_emails} emails, {total_whatsapp} WhatsApp). "
                f"{unread_messages} are still unread, and {important_emails} are important."
            ),
            "suggestions": [
                "Reply to important messages",
                "Review unread messages",
                "Generate AI summary of today's inbox"
            ]
        }

        # --- AI TASKS (Real from DB) ---
        tasks_qs = AssistantTask.objects.filter(user=user).order_by('-created_at')[:5]
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

        # --- PERFORMANCE (Sample / Mock for now) ---
        performance = {
            "response_time_avg": "12m",
            "ai_replies_sent": AssistantTask.objects.filter(user=user, task_type='reply', status='completed').count(),
            "important_threads": important_emails,
            "missed_messages": unread_messages,
            "trend": "+9%",
        }

        data = {
            "summary": ai_summary,
            "stats": {
                "total_messages": total_messages,
                "unread_messages": unread_messages,
                "important_emails": important_emails,
                "channel_breakdown": {
                    "email": total_emails,
                    "whatsapp": total_whatsapp,
                }
            },
            "tasks": ai_tasks,
            "performance": performance,
        }

        return Response(data)

    def get_time_of_day(self):
        hour = timezone.now().hour
        if hour < 12:
            return "morning"
        elif hour < 18:
            return "afternoon"
        return "evening"
