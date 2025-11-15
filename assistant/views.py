from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import AssistantTask
from .serializers import AssistantTaskSerializer, AssistantMessageSerializer
from rest_framework import generics, permissions
from .models import AssistantConfig, AssistantMessage, AssistantConfig
from .serializers import AssistantConfigSerializer
from whisprai.ai.gemini_client import get_ai_response
import json
from .ai_core.message_handler import MessageHandler
from django.utils import timezone

from rest_framework import generics, permissions, pagination
from rest_framework.response import Response
from django.utils import timezone


from rest_framework import generics, permissions, pagination
from .models import AssistantTask
from .serializers import AssistantTaskSerializer
from whisone.message_handler import process_user_message


class StandardResultsSetPagination(pagination.PageNumberPagination):
    """
    Custom pagination for assistant tasks.
    """
    page_size = 5  # default items per page
    page_size_query_param = 'page_size'  # allow client override ?page_size=20
    max_page_size = 50  # limit max results per page


class AssistantTaskListCreateView(generics.ListCreateAPIView):
    """
    Create or list assistant tasks (reminders, email_send, summarize, etc.)
    """
    serializer_class = AssistantTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return AssistantTask.objects.filter(
            user=self.request.user
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)



class AssistantTaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View, update, or delete a single assistant task.
    """
    serializer_class = AssistantTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AssistantTask.objects.filter(user=self.request.user)


class AssistantDueTaskView(generics.ListAPIView):
    """
    Lists tasks that are due for execution (e.g. reminders or scheduled emails).
    Useful for background schedulers (Celery/Django-Q).
    """
    serializer_class = AssistantTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = pagination.PageNumberPagination

    def get_queryset(self):
        now = timezone.now()
        return AssistantTask.objects.filter(
            user=self.request.user,
            status__in=["pending", "scheduled"],
            due_datetime__lte=now,
        )

    
# class AssistantChatView(generics.GenericAPIView):
#     permission_classes = [permissions.IsAuthenticated]
#     serializer_class = AssistantMessageSerializer


#     def get(self, request):
#         """
#         Fetch the user's recent chat history with the assistant.
#         You can limit the number of messages (e.g., last 20)
#         """
#         messages = AssistantMessage.objects.filter(user=request.user).order_by('-created_at')[:20]
#         serializer = self.get_serializer(messages, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def post(self, request):
#         user = request.user
#         prompt = request.data.get("message")

#         if not prompt:
#             return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

#         # Get assistant config
#         config, _ = AssistantConfig.objects.get_or_create(user=user)
        
#         # Save user message
#         AssistantMessage.objects.create(user=user, role="user", content=prompt)
#         # handler = MessageHandler(user=user)
#         # response_text = handler.handle(prompt)
#         response_text = process_user_message.delay(user.id, prompt)

#         response_text = response_text
#         print("Gemini response:", response_text)
#         # Save assistant response
#         reply = AssistantMessage.objects.create(user=user, role="assistant", content=response_text)

#         return Response({
#             "user_message": prompt,
#             "assistant_reply": response_text
#         })


class AssistantChatView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssistantMessageSerializer

    def get(self, request):
        messages = AssistantMessage.objects.filter(user=request.user).order_by('-created_at')[:20]
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user
        prompt = request.data.get("message")

        if not prompt:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get assistant config
        config, _ = AssistantConfig.objects.get_or_create(user=user)
        
        # Save user message
        AssistantMessage.objects.create(user=user, role="user", content=prompt)

        # Enqueue GPT processing task
        task = process_user_message.delay(user.id, prompt)
        print("Enqueued task ID:", task.id)

        # Return task ID so frontend can poll for result
        return Response({
            "user_message": prompt,
            "task_id": task.id,
            "status": "processing"
        }, status=status.HTTP_200_OK)


from celery.result import AsyncResult
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def get_assistant_response(request, task_id):
    task_result = AsyncResult(task_id)
    print("Checking task status for ID:", task_id, "Status:", task_result.status)
    print("Task info:", task_result.info)
    print("Is task ready?", task_result.ready())
    print("Is task successful?", task_result.state)

    if task_result.ready():
        # Get assistant reply from DB
        # Optional: you could also return result.result
        last_reply = AssistantMessage.objects.filter(user=request.user, role="assistant").order_by('-created_at').first()
        print("Last assistant reply:", last_reply.content if last_reply else "No reply found")
        return Response({
            "status": "done",
            "assistant_reply": last_reply.content if last_reply else "No reply"
        })
    else:
        return Response({"status": "pending"})



# from assistant.ai_core.message_handler import process_message  # Import the Celery task

# class AssistantChatView(generics.GenericAPIView):
#     permission_classes = [permissions.IsAuthenticated]
#     serializer_class = AssistantMessageSerializer

#     def get(self, request):
#         """
#         Fetch the user's recent chat history with the assistant.
#         You can limit the number of messages (e.g., last 20)
#         """
#         messages = AssistantMessage.objects.filter(user=request.user).order_by('-created_at')[:20]
#         serializer = self.get_serializer(messages, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def post(self, request):
#         user = request.user
#         prompt = request.data.get("message")

#         if not prompt:
#             return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

#         # Get assistant config (unused but kept for potential future use)
#         config, _ = AssistantConfig.objects.get_or_create(user=user)
        
#         # Save user message
#         AssistantMessage.objects.create(user=user, role="user", content=prompt)
        
#         # Process message using the Celery task (executes synchronously when called directly)
#         result = process_message(user.id, prompt)
#         response_text = result["reply"]
#         print("Assistant response:", response_text)
        
#         # Save assistant response
#         AssistantMessage.objects.create(user=user, role="assistant", content=response_text)

#         return Response({
#             "user_message": prompt,
#             "assistant_reply": response_text
#         })



class AssistantConfigView(generics.RetrieveUpdateAPIView):
    """
    View to get or update a user's AI Assistant configuration.
    """
    serializer_class = AssistantConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj, _ = AssistantConfig.objects.get_or_create(user=self.request.user)
        return obj


# Non-API view for natural language processing (e.g., POST /process-query/)
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Automation
from .serializers import AutomationSerializer


class AutomationListCreateView(APIView):
    """Handles listing all user automations and creating new ones."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        automations = Automation.objects.filter(user=request.user)
        serializer = AutomationSerializer(automations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AutomationSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AutomationDetailView(APIView):
    """Handles retrieving, updating, and deleting a single automation."""

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, user, pk):
        return get_object_or_404(Automation, pk=pk, user=user)

    def get(self, request, pk):
        automation = self.get_object(request.user, pk)
        serializer = AutomationSerializer(automation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        automation = self.get_object(request.user, pk)
        serializer = AutomationSerializer(automation, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        automation = self.get_object(request.user, pk)
        automation.delete()
        return Response({"detail": "Automation deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class AutomationTriggerView(APIView):
    """Manually trigger an automation."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        automation = get_object_or_404(Automation, pk=pk, user=request.user)
        if not automation.is_active:
            return Response({"detail": "Automation is inactive."}, status=status.HTTP_400_BAD_REQUEST)

        automation.mark_triggered()
        return Response(
            {
                "detail": f"Automation '{automation.name}' triggered successfully.",
                "last_triggered_at": automation.last_triggered_at,
            },
            status=status.HTTP_200_OK,
        )


class AutomationToggleView(APIView):
    """Enable or disable an automation."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        automation = get_object_or_404(Automation, pk=pk, user=request.user)
        automation.is_active = not automation.is_active
        automation.save(update_fields=["is_active"])
        return Response(
            {"detail": f"Automation is now {'active' if automation.is_active else 'inactive'}."},
            status=status.HTTP_200_OK,
        )
