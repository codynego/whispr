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
# ----------------------
class NoteListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        notes = Note.objects.filter(user=request.user)
        serializer = NoteSerializer(notes, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = NoteSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NoteDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Note.objects.get(pk=pk, user=user)
        except Note.DoesNotExist:
            return None

    def get(self, request, pk):
        note = self.get_object(pk, request.user)
        if not note:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = NoteSerializer(note)
        return Response(serializer.data)

    def put(self, request, pk):
        note = self.get_object(pk, request.user)
        if not note:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = NoteSerializer(note, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        note = self.get_object(pk, request.user)
        if not note:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ----------------------
# Reminders
# ----------------------
class ReminderListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        reminders = Reminder.objects.filter(user=request.user)
        serializer = ReminderSerializer(reminders, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ReminderSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReminderDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Reminder.objects.get(pk=pk, user=user)
        except Reminder.DoesNotExist:
            return None

    def get(self, request, pk):
        reminder = self.get_object(pk, request.user)
        if not reminder:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ReminderSerializer(reminder)
        return Response(serializer.data)

    def put(self, request, pk):
        reminder = self.get_object(pk, request.user)
        if not reminder:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = ReminderSerializer(reminder, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        reminder = self.get_object(pk, request.user)
        if not reminder:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        reminder.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ----------------------
# Todos
# ----------------------
class TodoListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        todos = Todo.objects.filter(user=request.user)
        serializer = TodoSerializer(todos, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TodoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TodoDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Todo.objects.get(pk=pk, user=user)
        except Todo.DoesNotExist:
            return None

    def get(self, request, pk):
        todo = self.get_object(pk, request.user)
        if not todo:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = TodoSerializer(todo)
        return Response(serializer.data)

    def put(self, request, pk):
        todo = self.get_object(pk, request.user)
        if not todo:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = TodoSerializer(todo, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        todo = self.get_object(pk, request.user)
        if not todo:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        todo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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


# === Gmail OAuth Callback ===
class GmailOAuthCallbackView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        code = request.GET.get("code")
        if not code:
            return JsonResponse({"error": "Missing authorization code"}, status=400)

        user = request.user

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

        # Extract Gmail account email
        decoded_token = jwt.decode(creds.id_token, options={"verify_signature": False})
        email_address = decoded_token.get("email")

        if not email_address:
            return JsonResponse({"error": "Could not extract email from token"}, status=400)

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
