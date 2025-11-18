from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Note, Reminder, Todo, Integration
from .serializers import NoteSerializer, ReminderSerializer, TodoSerializer, IntegrationSerializer
from .executor import Executor
from .task_planner import TaskPlanner
from .response_generator import ResponseGenerator
# email_views.py
from rest_framework import generics, permissions
from django.http import JsonResponse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from google_auth_oauthlib.flow import Flow
import jwt, json
# unified/views/integration_views.py

from rest_framework import generics, permissions, status




# ----------------------
# Notes
class NoteListCreateView(generics.ListCreateAPIView):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class NoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)


# ======================
# REMINDERS
# ======================
class ReminderListCreateView(generics.ListCreateAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReminderDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user)


# ======================
# TODOS
# ======================
class TodoListCreateView(generics.ListCreateAPIView):
    serializer_class = TodoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Todo.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TodoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TodoSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return Todo.objects.filter(user=self.request.user)

# ----------------------
# Whisone NLP Endpoint
# ----------------------
class WhisoneMessageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user_message = request.data.get("message")
        user = request.user

        # 1️⃣ Plan tasks
        planner = TaskPlanner(openai_api_key="YOUR_API_KEY")
        task_plan = planner.plan_tasks(user_message)

        # 2️⃣ Execute tasks
        executor = Executor(user)
        executor_results = executor.execute_task(task_plan)

        # 3️⃣ Generate response
        response_gen = ResponseGenerator(openai_api_key="YOUR_API_KEY")
        response_text = response_gen.generate_response(user_message, executor_results)

        return Response({
            "task_plan": task_plan,
            "executor_results": executor_results,
            "response": response_text
        })




# === CONFIG ===
REDIRECT_URI = "https://www.whisone.app/dashboard/settings/integrations/callbacks"
CLIENT_SECRET_FILE = "unified/credentials/client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
    "https://www.googleapis.com/auth/calendar.events",
]


# === Gmail OAuth Start ===
class GmailOAuthInitView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # encode user ID into state
        state_data = {"uid": urlsafe_base64_encode(force_bytes(request.user.id))}
        state_str = json.dumps(state_data)
        print("Gmail OAuth init for user:", request.user.id)

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        print("Generated OAuth flow")

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state_str,
        )
        print("Gmail OAuth init URL:", auth_url)

        return JsonResponse({"url": auth_url})


# === Gmail OAuth Callback ===
class GmailOAuthCallbackView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        print("Gmail OAuth callback received")
        code = request.GET.get("code")
        if not code:
            return JsonResponse({"error": "Missing authorization code"}, status=400)

        user = request.user

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRET_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        print("Fetching token with code:", code)

        try:
            flow.fetch_token(code=code)
        except Exception as e:
            return JsonResponse({"error": f"Token exchange failed: {str(e)}"}, status=400)

        creds = flow.credentials

        # Extract Gmail account email
        decoded_token = jwt.decode(creds.id_token, options={"verify_signature": False})
        email_address = decoded_token.get("email")

        if not email_address:
            return JsonResponse({"error": "Could not extract email from token"}, status=400)
        print("Gmail OAuth successful for:", email_address)

        # === Save Gmail integration ===
        integration, created = Integration.objects.update_or_create(
            user=user,
            provider="gmail",
            external_id=email_address,
            defaults={
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "expires_at": creds.expiry,
                "is_active": True,
            },
        )

        return JsonResponse({
            "message": "Gmail connected successfully!",
            "integration_id": integration.id,
            "email": email_address,
        })



# ========== LIST INTEGRATIONS ==========
class IntegrationListView(generics.ListAPIView):
    """
    List all integrations for the logged-in user.
    """
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Integration.objects.filter(user=self.request.user)


# ========== DELETE INTEGRATION ==========
class IntegrationDeleteView(generics.DestroyAPIView):
    """
    Permanently delete a user's integration.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = IntegrationSerializer

    def get_queryset(self):
        # Limit delete action to only the user's integrations
        return Integration.objects.filter(user=self.request.user)


# ========== DEACTIVATE INTEGRATION ==========
class IntegrationDeactivateView(generics.GenericAPIView):
    """
    Set is_active = False for an integration.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = IntegrationSerializer

    def post(self, request, pk):
        try:
            integration = Integration.objects.get(id=pk, user=request.user)
        except Integration.DoesNotExist:
            return Response({"error": "Integration not found"}, status=404)

        integration.is_active = False
        integration.save(update_fields=["is_active"])

        return Response({"message": "Integration deactivated"}, status=200)




from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .models import (
    Reminder, Note, Todo, Integration, AutomationRule,
    KnowledgeVaultEntry, UserPreference
)

# If you have service classes:
# from .services.gmail_service import GmailService
# from .services.calendar_service import GoogleCalendarService


@login_required
def dashboard_overview(request):
    user = request.user
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timezone.timedelta(days=1)

    # -----------------------------
    # 1. Reminders (Today + upcoming)
    # -----------------------------
    reminders_today = Reminder.objects.filter(
        user=user,
        remind_at__gte=today_start,
        remind_at__lt=today_end,
        completed=False
    ).order_by("remind_at")

    upcoming_reminders = Reminder.objects.filter(
        user=user,
        remind_at__gte=today_end,
        completed=False
    ).order_by("remind_at")[:5]

    # -----------------------------
    # 2. Todos (Today and pending)
    # -----------------------------
    todos_today = Todo.objects.filter(
        user=user,
        done=False,
        created_at__gte=today_start
    ).order_by("created_at")

    pending_todos = Todo.objects.filter(
        user=user,
        done=False
    ).order_by("created_at")[:10]

    # -----------------------------
    # 3. Notes (recent)
    # -----------------------------
    recent_notes = Note.objects.filter(
        user=user
    ).order_by("-created_at")[:5]

    # -----------------------------
    # 4. Integrations
    # -----------------------------
    integrations = Integration.objects.filter(user=user, is_active=True)

    # -----------------------------
    # 5. Automations
    # -----------------------------
    automations = AutomationRule.objects.filter(
        user=user,
        is_active=True
    ).order_by("-created_at")[:5]

    # -----------------------------
    # 6. Knowledge Vault (recent insights)
    # -----------------------------
    knowledge_entries = KnowledgeVaultEntry.objects.filter(
        user=user
    ).order_by("-timestamp")[:10]

    # -----------------------------
    # 7. User Preferences
    # -----------------------------
    try:
        preference_model = user.preference_model
        user_preferences = preference_model.preferences
    except UserPreference.DoesNotExist:
        user_preferences = {}

    # -----------------------------
    # 8. Important Emails (via Gmail)
    # -----------------------------
    important_emails = []
    gmail_integration = integrations.filter(provider="gmail").first()

    if gmail_integration:
        try:
            gmail = GmailService(gmail_integration)
            important_emails = gmail.get_important_emails(limit=5)
        except Exception:
            important_emails = []

    # -----------------------------
    # 9. Calendar Events (today)
    # -----------------------------
    today_events = []
    calendar_integration = integrations.filter(provider="google_calendar").first()

    if calendar_integration:
        try:
            calendar = GoogleCalendarService(calendar_integration)
            today_events = calendar.get_events(time_min=today_start, time_max=today_end)
        except Exception:
            today_events = []

    # -----------------------------
    # Package Data for Template or JSON
    # -----------------------------
    data = {
        "reminders_today": list(reminders_today.values()),
        "upcoming_reminders": list(upcoming_reminders.values()),

        "todos_today": list(todos_today.values()),
        "pending_todos": list(pending_todos.values()),

        "recent_notes": list(recent_notes.values("id", "content", "created_at")),

        "integrations": list(integrations.values("provider", "external_id", "is_active")),
        "automations": list(automations.values("id", "name", "trigger_type", "is_active")),

        "knowledge_recent": [
            {
                "id": k.id,
                "entities": k.entities,
                "summary": k.summary,
                "timestamp": k.timestamp,
            }
            for k in knowledge_entries
        ],

        "user_preferences": user_preferences,

        "important_emails": important_emails,
        "today_events": today_events,
    }

    # If you want API response:
    return JsonResponse({"status": "success", "overview": data}, safe=False)
