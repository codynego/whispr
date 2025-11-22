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
from datetime import date
from rest_framework.permissions import IsAuthenticated

from whisone.models import DailySummary, Reminder, Todo, Note
from .serializers import DailySummarySerializer
from rest_framework import generics, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q



# ======================
# Standard Pagination (20 items per page)
# ======================
class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ======================
# NOTES
# ======================
class NoteListCreateView(generics.ListCreateAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    # Enable filtering, search, ordering
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    # Filter by date
    filterset_fields = {
        'created_at': ['gte', 'lte', 'date', 'gt', 'lt'],
        'updated_at': ['gte', 'lte'],
    }

    # Full-text search in content
    search_fields = ['content']

    # Allowed ordering
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']  # newest first

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)


class NoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return Note.objects.filter(user=self.request.user)


# ======================
# REMINDERS
# ======================
class ReminderListCreateView(generics.ListCreateAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = {
        'remind_at': ['exact', 'gte', 'lte', 'gt', 'lt', 'date'],
        'completed': ['exact'],
        'created_at': ['gte', 'lte', 'date'],
    }

    search_fields = ['text']
    ordering_fields = ['remind_at', 'created_at', 'completed']
    ordering = ['remind_at']  # soonest first

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReminderDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user)


# ======================
# TODOS
# ======================
class TodoListCreateView(generics.ListCreateAPIView):
    serializer_class = TodoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = {
        'done': ['exact'],
        'created_at': ['gte', 'lte', 'date'],
    }

    search_fields = ['task']
    ordering_fields = ['created_at', 'done']
    ordering = ['-created_at']

    def get_queryset(self):
        return Todo.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TodoDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TodoSerializer
    permission_classes = [IsAuthenticated]
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



class OverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = date.today()

        # Fetch today's summary
        try:
            summary = DailySummary.objects.get(user=user, summary_date=today)
            summary_data = DailySummarySerializer(summary).data
        except DailySummary.DoesNotExist:
            summary_data = {
                "id": None,
                "content": "",  # ← always a string, never null
                "summary_date": str(today),
            }

        total_reminders = Reminder.objects.filter(user=user).count()
        completed_todos = Todo.objects.filter(user=user, done=True).count()
        recent_notes = Note.objects.filter(user=user).order_by('-created_at')[:6]

        data = {
            "has_summary": summary_data["id"] is not None,
            "daily_summary": summary_data,  # ← always an object with .content
            "stats": {
                "total_reminders": total_reminders,
                "completed_todos": completed_todos,
            },
            "recent_notes": [
                {
                    "id": note.id,
                    "content": note.content or "",
                    "created_at": note.created_at.isoformat(),
                }
                for note in recent_notes
            ]
        }

        return Response(data)