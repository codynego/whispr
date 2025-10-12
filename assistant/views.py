from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import AssistantTask
from .serializers import AssistantTaskSerializer, CreateAssistantTaskSerializer, AssistantMessageSerializer
from .tasks import process_assistant_task
from rest_framework import generics, permissions
from .models import AssistantConfig, AssistantMessage, AssistantConfig
from .serializers import AssistantConfigSerializer
from whisprai.ai.gemini_client import get_gemini_response
import json
from .ai_core.message_handler import MessageHandler


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



class AssistantTaskListView(generics.ListAPIView):
    """List all assistant tasks for the authenticated user"""
    serializer_class = AssistantTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = AssistantTask.objects.filter(user=self.request.user)
        
        # Filter by task type
        task_type = self.request.query_params.get('task_type')
        if task_type:
            queryset = queryset.filter(task_type=task_type)
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        return queryset


class AssistantTaskDetailView(generics.RetrieveAPIView):
    """Retrieve an assistant task"""
    serializer_class = AssistantTaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return AssistantTask.objects.filter(user=self.request.user)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def create_task(request):
    """Create and process an assistant task"""
    serializer = CreateAssistantTaskSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    # Create task
    task = AssistantTask.objects.create(
        user=request.user,
        task_type=serializer.validated_data['task_type'],
        input_text=serializer.validated_data['input_text'],
        context=serializer.validated_data.get('context'),
        related_email_id=serializer.validated_data.get('related_email_id')
    )
    
    # Trigger async processing
    celery_task = process_assistant_task.delay(task.id)
    
    return Response({
        'task': AssistantTaskSerializer(task).data,
        'celery_task_id': celery_task.id,
        'message': 'Task created and queued for processing'
    }, status=status.HTTP_201_CREATED)
