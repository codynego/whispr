from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import AssistantTask
from .serializers import AssistantTaskSerializer, CreateAssistantTaskSerializer
from .tasks import process_assistant_task


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
