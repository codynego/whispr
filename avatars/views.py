from rest_framework import generics, permissions
from .models import (
    Avatar, AvatarSource, AvatarTrainingJob, AvatarMemoryChunk, 
    AvatarConversation, AvatarMessage, AvatarAnalytics, AvatarSettings,
)
from .serializers import (
    AvatarSerializer, AvatarSourceSerializer, AvatarTrainingJobSerializer, 
    AvatarConversationSerializer, 
    AvatarMessageSerializer, AvatarAnalyticsSerializer, AvatarSettingsSerializer,
    AvatarMemoryChunkSerializer
)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from avatars.tasks import train_avatar_task 
from avatars.services.chat_engine import generate_avatar_reply 

from django.db.models import Q
import uuid

# --- Helper Functions ---
def get_avatar_by_handle_and_owner(handle, user):
    """Retrieves an Avatar by handle, ensuring the user is the owner."""
    return get_object_or_404(Avatar, handle=handle, owner=user)

def get_avatar_by_handle_public(handle):
    """Retrieves an Avatar by handle only if its settings mark it as public."""
    # Assumes AvatarSettings is related via a one-to-one field named 'settings'
    return get_object_or_404(Avatar.objects.select_related('settings'), handle=handle, settings__visibility=True)

# ----------------------------------------------------------------------
# 1. NEW HANDLE-BASED CONVENIENCE VIEWS (Used by the Configuration UI)
# ----------------------------------------------------------------------

class AvatarRetrieveByHandleView(generics.RetrieveAPIView):
    """Allows retrieval of Avatar details (including nested settings/analytics) by handle."""
    serializer_class = AvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        handle = self.kwargs.get('handle')
        return get_avatar_by_handle_and_owner(handle, self.request.user)

class AvatarSettingsByHandleView(generics.RetrieveUpdateAPIView):
    """Allows retrieval and update of AvatarSettings via the Avatar handle."""
    serializer_class = AvatarSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        handle = self.kwargs.get('handle')
        avatar = get_avatar_by_handle_and_owner(handle, self.request.user)
        # Note: AvatarSettings should be auto-created when the Avatar is created
        return get_object_or_404(AvatarSettings, avatar=avatar)

class AvatarAnalyticsByHandleView(generics.RetrieveAPIView):
    """Allows retrieval of AvatarAnalytics via the Avatar handle."""
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        handle = self.kwargs.get('handle')
        avatar = get_avatar_by_handle_and_owner(handle, self.request.user)
        # Note: AvatarAnalytics should be auto-created when the Avatar is created
        return get_object_or_404(AvatarAnalytics, avatar=avatar)

class AvatarSourceListCreateByHandleView(generics.ListCreateAPIView):
    """Allows listing and creating AvatarSources for a specific Avatar handle."""
    serializer_class = AvatarSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        handle = self.kwargs.get('handle')
        avatar = get_avatar_by_handle_and_owner(handle, self.request.user)
        return AvatarSource.objects.filter(avatar=avatar)

    def perform_create(self, serializer):
        handle = self.kwargs.get('handle')
        avatar = get_avatar_by_handle_and_owner(handle, self.request.user)
        serializer.save(avatar=avatar)

# ----------------------------------------------------------------------
# 2. CHAT, TRAINING, AND HISTORY VIEWS
# ----------------------------------------------------------------------

class AvatarChatView(APIView):
    """Endpoint for visitors to chat with an Avatar (Async request)."""
    permission_classes = [permissions.AllowAny]

    def post(self, request, handle):
        try:
            avatar = get_avatar_by_handle_public(handle)
        except Exception:
            return Response({"error": "Avatar not found or not public."}, status=status.HTTP_404_NOT_FOUND)

        visitor_id = request.data.get("visitor_id") or request.session.session_key
        message_text = request.data.get("message")

        if not message_text or not visitor_id:
            return Response({"error": "Message and visitor_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create an active conversation
        conversation, _ = AvatarConversation.objects.get_or_create(
            avatar=avatar, visitor_id=visitor_id, ended_at=None
        )

        # Save visitor message
        visitor_message = AvatarMessage.objects.create(
            conversation=conversation, role="visitor", content=message_text
        )

        # Trigger Celery task
        task_id = generate_avatar_reply.delay(
            conversation_id=str(conversation.id),
            user_message_id=str(visitor_message.id)
        )
        
        return Response({
            "conversation_id": str(conversation.id),
            "task_id": str(task_id), # Return the Celery task ID for polling
        }, status=status.HTTP_202_ACCEPTED)

class AvatarTrainView(APIView):
    """Triggers the asynchronous Celery training task for an Avatar."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, handle):
        avatar = get_avatar_by_handle_and_owner(handle, request.user)

        job = AvatarTrainingJob.objects.create(
            avatar=avatar, status="pending" 
        )

        train_avatar_task.delay(str(job.id))

        return Response({
            "job_id": str(job.id), "status": job.status,
            "message": f"Training for avatar '{avatar.name}' has been queued."
        }, status=status.HTTP_201_CREATED)

class AvatarTrainingJobStatusView(generics.RetrieveAPIView):
    """Retrieves the status of a specific training or chat job (for polling)."""
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    lookup_field = "id" # Matches the <uuid:id> in urls.py
    permission_classes = [permissions.AllowAny] 
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # Attach progress logic (conceptual)
        if data['status'] == 'started': data['progress'] = 30
        elif data['status'] == 'processing': data['progress'] = 75
        elif data['status'] == 'success': data['progress'] = 100
        
        # If chat job is complete, return the assistant reply
        if hasattr(instance, 'task_type') and instance.task_type == 'chat_reply' and data['status'] == 'success':
            last_message = AvatarMessage.objects.filter(conversation__avatar=instance.avatar).order_by('-created_at').first()
            if last_message and last_message.role == 'assistant':
                data['assistant_reply'] = last_message.content

        return Response(data)


class AvatarConversationHistoryView(generics.ListAPIView):
    """Retrieves the conversation history for a visitor/avatar pair, primarily for the public chat interface."""
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        handle = self.kwargs.get('handle')
        visitor_id = self.request.query_params.get('visitor_id')

        avatar = get_object_or_404(Avatar, handle=handle)

        # Get the latest ongoing conversation for this pair
        conversation = AvatarConversation.objects.filter(
            avatar=avatar, visitor_id=visitor_id
        ).order_by('-started_at').first()

        if not conversation: return AvatarMessage.objects.none()

        return AvatarMessage.objects.filter(conversation=conversation).order_by('created_at')


class AvatarConversationTakeoverView(APIView):
    """Allows the Avatar owner to take over a live conversation by ID."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        conversation = get_object_or_404(AvatarConversation, pk=pk)
        
        # Security check: ensure the authenticated user owns the avatar
        if conversation.avatar.owner != request.user:
            return Response({"error": "You do not own this conversation's avatar."}, status=status.HTTP_403_FORBIDDEN)

        if conversation.taken_over_by_owner:
             return Response({"message": "Conversation already under human control."}, status=status.HTTP_200_OK)

        conversation.taken_over_by_owner = True
        conversation.save(update_fields=['taken_over_by_owner'])

        # Log the takeover action in the chat history
        AvatarMessage.objects.create(
            conversation=conversation, role="owner", content=f"Human owner has taken over the chat. 👋"
        )

        return Response({"status": "takeover_active"}, status=status.HTTP_200_OK)

# ----------------------------------------------------------------------
# 3. ORIGINAL UUID-BASED VIEWS (Standard CRUD operations)
# ----------------------------------------------------------------------

class AvatarListCreateView(generics.ListCreateAPIView):
    """List Avatars owned by the current user, or create a new one."""
    queryset = Avatar.objects.all()
    serializer_class = AvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class AvatarRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, Update, or Destroy an Avatar by UUID (PK)."""
    queryset = Avatar.objects.all()
    serializer_class = AvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)


class AvatarSourceListCreateView(generics.ListCreateAPIView):
    """List all AvatarSources, or create a new one."""
    queryset = AvatarSource.objects.all()
    serializer_class = AvatarSourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Note: Requires client to supply 'avatar' ID in the POST request body.


class AvatarSourceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, Update, or Destroy an AvatarSource by UUID (PK)."""
    queryset = AvatarSource.objects.all()
    serializer_class = AvatarSourceSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarTrainingJobListView(generics.ListAPIView):
    """List all AvatarTrainingJobs."""
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarTrainingJobDetailView(generics.RetrieveAPIView):
    """Retrieve details of an AvatarTrainingJob by UUID (PK)."""
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarMemoryChunkListView(generics.ListAPIView):
    """List all AvatarMemoryChunks."""
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarMemoryChunkDetailView(generics.RetrieveAPIView):
    """Retrieve details of an AvatarMemoryChunk by UUID (PK)."""
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarConversationListCreateView(generics.ListCreateAPIView):
    """List or Create AvatarConversations."""
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.AllowAny]


class AvatarConversationRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    """Retrieve or Destroy an AvatarConversation by UUID (PK)."""
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.AllowAny]


class AvatarMessageListCreateView(generics.ListCreateAPIView):
    """List or Create AvatarMessages."""
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]


class AvatarMessageRetrieveView(generics.RetrieveAPIView):
    """Retrieve an AvatarMessage by UUID (PK)."""
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]


class AvatarAnalyticsListView(generics.ListAPIView):
    """List all AvatarAnalytics records."""
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarAnalyticsDetailView(generics.RetrieveAPIView):
    """Retrieve an AvatarAnalytics record by UUID (PK)."""
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarSettingsRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or Update AvatarSettings by UUID (PK)."""
    queryset = AvatarSettings.objects.all()
    serializer_class = AvatarSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]