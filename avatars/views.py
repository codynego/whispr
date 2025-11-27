# whisone/avatars/views.py
from rest_framework import generics, permissions
from .models import (
    Avatar, AvatarSource, AvatarTrainingJob, AvatarMemoryChunk, 
    AvatarConversation, AvatarMessage, AvatarAnalytics, AvatarSettings,
)
from .serializers import (
    AvatarSerializer, AvatarSourceSerializer, AvatarTrainingJobSerializer, 
    AvatarMemoryChunkSerializer, AvatarConversationSerializer, 
    AvatarMessageSerializer, AvatarAnalyticsSerializer, AvatarSettingsSerializer,
)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from avatars.tasks import train_avatar_task 
from avatars.services.chat_engine import generate_avatar_reply # Assuming this returns task_id now, or reply for sync
from datetime import datetime
from django.db.models import Q, Max # For analytics and history
import uuid

# --- Helper Functions ---
def get_avatar_by_handle_and_owner(handle, user):
    return get_object_or_404(Avatar, handle=handle, owner=user)

def get_avatar_by_handle_public(handle):
    return get_object_or_404(Avatar.objects.select_related('settings'), handle=handle, settings__visibility=True)

# ----------------------------------------------------------------------
# NEW HANDLE-BASED CONVENIENCE VIEWS (Used by the UI)
# ----------------------------------------------------------------------

class AvatarRetrieveByHandleView(generics.RetrieveAPIView):
    """Allows retrieval of Avatar details (including nested settings) by handle."""
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
        return get_object_or_404(AvatarSettings, avatar=avatar)

class AvatarAnalyticsByHandleView(generics.RetrieveAPIView):
    """Allows retrieval of AvatarAnalytics via the Avatar handle."""
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        handle = self.kwargs.get('handle')
        avatar = get_avatar_by_handle_and_owner(handle, self.request.user)
        # Assuming AvatarAnalytics is created alongside Avatar
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
        # Assuming is_config_saved flag is set here (logic omitted)


# ----------------------------------------------------------------------
# CHAT/TRAIN/HISTORY VIEWS
# ----------------------------------------------------------------------

class AvatarChatView(APIView):
    """
    Endpoint for visitors to chat with an Avatar.
    Note: Modified to be ASYNC and return a task_id for polling.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, handle):
        # Use get_avatar_by_handle_public to ensure the avatar is public
        try:
            avatar = get_avatar_by_handle_public(handle)
        except Exception:
            return Response({"error": "Avatar not found or not public."}, status=status.HTTP_404_NOT_FOUND)

        visitor_id = request.data.get("visitor_id") or request.session.session_key
        message_text = request.data.get("message")

        if not message_text or not visitor_id:
            return Response({"error": "Message and visitor_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        conversation, _ = AvatarConversation.objects.get_or_create(
            avatar=avatar,
            visitor_id=visitor_id,
            ended_at=None
        )

        visitor_message = AvatarMessage.objects.create(
            conversation=conversation,
            role="visitor",
            content=message_text
        )

        # Trigger Celery task (ASYNC)
        task_id = generate_avatar_reply.delay(
            conversation_id=str(conversation.id),
            user_message_id=str(visitor_message.id)
        )
        
        # NOTE: generate_avatar_reply now needs to be an async task that returns its own ID
        return Response({
            "conversation_id": str(conversation.id),
            "task_id": str(task_id), # Return the Celery task ID for polling
        }, status=status.HTTP_202_ACCEPTED) # 202 Accepted for async job

class AvatarTrainView(APIView):
    """Triggers the asynchronous Celery training task."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, handle):
        avatar = get_avatar_by_handle_and_owner(handle, request.user)

        job = AvatarTrainingJob.objects.create(
            avatar=avatar,
            status="pending" # Use pending/queued before task starts
        )

        train_avatar_task.delay(str(job.id))

        return Response({
            "job_id": str(job.id),
            "status": job.status,
            "message": f"Training for avatar '{avatar.name}' has been queued."
        }, status=status.HTTP_201_CREATED)

class AvatarTrainingJobStatusView(generics.RetrieveAPIView):
    """Retrieves the status of a specific training job (for polling)."""
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    lookup_field = "id"
    # Allow public chat polling with a unique job ID, but restrict detailed job access to owner
    permission_classes = [permissions.AllowAny] 
    
    # Override retrieve to add dummy progress for UI testing
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        data = serializer.data
        
        # --- Conceptual Progress Logic for UI ---
        # This should come from Celery backend or Redis, but here for UI test:
        if data['status'] == 'started':
            data['progress'] = 30
        elif data['status'] == 'processing':
            data['progress'] = 75
        elif data['status'] == 'success':
            data['progress'] = 100
        # --- End Conceptual Logic ---

        # If this is a chat response task, return the last assistant message
        if instance.task_type == 'chat_reply' and data['status'] == 'done': # Assuming AvatarTrainingJob model is reused for chat tasks
            last_message = AvatarMessage.objects.filter(conversation__avatar=instance.avatar).order_by('-created_at').first()
            if last_message and last_message.role == 'assistant':
                data['assistant_reply'] = last_message.content

        return Response(data)


class AvatarConversationHistoryView(generics.ListAPIView):
    """Retrieves the conversation history for a visitor/avatar pair."""
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        handle = self.kwargs.get('handle')
        visitor_id = self.request.query_params.get('visitor_id')

        avatar = get_object_or_404(Avatar, handle=handle)

        # Get the latest conversation for this visitor_id and avatar
        conversation = AvatarConversation.objects.filter(
            avatar=avatar,
            visitor_id=visitor_id
        ).order_by('-started_at').first()

        if not conversation:
            return AvatarMessage.objects.none()

        return AvatarMessage.objects.filter(conversation=conversation).order_by('created_at')


class AvatarConversationTakeoverView(APIView):
    """Allows the Avatar owner to take over a live conversation."""
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

        # Create a notification message in the conversation stream
        AvatarMessage.objects.create(
            conversation=conversation,
            role="owner",
            content=f"Human owner has taken over the chat. 👋"
        )

        return Response({"status": "takeover_active"}, status=status.HTTP_200_OK)

# ----------------------------------------------------------------------
# ORIGINAL UUID-BASED VIEWS (Kept for completeness)
# ----------------------------------------------------------------------

class AvatarListCreateView(generics.ListCreateAPIView):
    queryset = Avatar.objects.all()
    serializer_class = AvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class AvatarRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Avatar.objects.all()
    serializer_class = AvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

class AvatarSourceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AvatarSource.objects.all()
    serializer_class = AvatarSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

class AvatarTrainingJobListView(generics.ListAPIView):
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]

class AvatarTrainingJobDetailView(generics.RetrieveAPIView):
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]

class AvatarMemoryChunkListView(generics.ListAPIView):
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]

class AvatarMemoryChunkDetailView(generics.RetrieveAPIView):
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]

class AvatarConversationListCreateView(generics.ListCreateAPIView):
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.AllowAny]

class AvatarConversationRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.AllowAny]

class AvatarMessageListCreateView(generics.ListCreateAPIView):
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]

class AvatarMessageRetrieveView(generics.RetrieveAPIView):
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]

class AvatarAnalyticsListView(generics.ListAPIView):
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

class AvatarAnalyticsDetailView(generics.RetrieveAPIView):
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

class AvatarSettingsRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    queryset = AvatarSettings.objects.all()
    serializer_class = AvatarSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]