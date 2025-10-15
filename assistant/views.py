from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import AssistantTask
from .serializers import AssistantTaskSerializer, AssistantMessageSerializer
from rest_framework import generics, permissions
from .models import AssistantConfig, AssistantMessage, AssistantConfig
from .serializers import AssistantConfigSerializer
from whisprai.ai.gemini_client import get_gemini_response
import json
from .ai_core.message_handler import MessageHandler
from django.utils import timezone

class AssistantTaskListCreateView(generics.ListCreateAPIView):
    """
    Create or list assistant tasks (reminders, email_send, summarize, etc.)
    """
    serializer_class = AssistantTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AssistantTask.objects.filter(user=self.request.user).order_by("-created_at")

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

    def get_queryset(self):
        now = timezone.now()
        return AssistantTask.objects.filter(
            user=self.request.user,
            status__in=["pending", "scheduled"],
            due_datetime__lte=now,
        )


class AssistantChatView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AssistantMessageSerializer


    def get(self, request):
        """
        Fetch the user's recent chat history with the assistant.
        You can limit the number of messages (e.g., last 20)
        """
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
        handler = MessageHandler(user=user)
        response_text = handler.handle(prompt)
        print("Handler response:", response_text)

        # # Build personalized context
        # system_prompt = f"""
        # You are an AI assistant for {user.email}.
        # Tone: {config.tone}.
        # Instructions: {config.custom_instructions or 'Be helpful and concise.'}
        # Respond based on user's message below:
        # """

        # full_prompt = f"{system_prompt}\nUser: {prompt}"

        # # Call Gemini
        # response_text = get_gemini_response(
        #     prompt,
        #     user_id=request.user.id,
        #     temperature=config.temperature,
        #     max_output_tokens=config.max_response_length
        # )
        response_text = response_text["reply"]
        print("Gemini response:", response_text)
        # Save assistant response
        reply = AssistantMessage.objects.create(user=user, role="assistant", content=response_text)

        return Response({
            "user_message": prompt,
            "assistant_reply": response_text
        })



class AssistantConfigView(generics.RetrieveUpdateAPIView):
    """
    View to get or update a user's AI Assistant configuration.
    """
    serializer_class = AssistantConfigSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        obj, _ = AssistantConfig.objects.get_or_create(user=self.request.user)
        return obj


