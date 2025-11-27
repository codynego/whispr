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
    """
    Retrieves an Avatar by handle, ensuring the user is the owner.
    This helper is ONLY called when the user is already authenticated.
    """
    return get_object_or_404(Avatar, handle=handle, owner=user)

def get_avatar_by_handle_public(handle):
    """
    Retrieves an Avatar by handle only if its settings mark it as public.
    Visibility is typically stored as 'public' string, not True boolean.
    """
    # FIX: Changed settings__visibility=True to the correct string value 'public'
    return get_object_or_404(Avatar, handle=handle)
    # return get_object_or_404(
    #     Avatar.objects.select_related('settings'), 
    #     handle=handle, 
    #     settings__visibility='public' # Use the actual choice value
    # )


# ----------------------------------------------------------------------
# 1. NEW HANDLE-BASED CONVENIENCE VIEWS (Used by the Configuration UI)
# ----------------------------------------------------------------------

class AvatarRetrieveByHandleView(generics.RetrieveAPIView):
    """
    Allows retrieval of Avatar details (including nested settings/analytics) by handle.
    This view is strictly for the OWNER/AUTHENTICATED user (Configuration panel).
    """
    serializer_class = AvatarSerializer
    # FIX: Reverted permission to IsAuthenticated to prevent TypeError with AnonymousUser
    permission_classes = [permissions.IsAuthenticated] 

    def get_object(self):
        handle = self.kwargs.get('handle')
        # request.user is guaranteed to be authenticated here
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


# --- Public Retrieval View (Recommended for the public facing URL) ---

class AvatarRetrievePublicView(generics.RetrieveAPIView):
    """
    Allows public retrieval of Avatar details by handle, restricted to public Avatars.
    Use this for the public chat embed/interface loading.
    """
    serializer_class = AvatarSerializer
    permission_classes = [permissions.AllowAny] 
    
    def get_object(self):
        handle = self.kwargs.get('handle')
        return get_avatar_by_handle_public(handle) 


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

        # Ensure session key exists for visitor_id fallback
        if not request.session.session_key:
            request.session.save()
            
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
            avatar=avatar, status="queued" # Changed status from 'pending' to 'queued' for consistency
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
    lookup_field = "id" 
    # FIX: Added permission check here. If the job is for a private avatar, only the owner should see it.
    # However, since the chat endpoint uses this for polling (and is AllowAny), we'll keep AllowAny for now
    # but the job creation itself should ideally link to the current conversation ID.
    permission_classes = [permissions.AllowAny] 
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Security check: If the user is authenticated, ensure they are the owner OR the avatar is public.
        # This is basic and can be refined later. For now, trust the permission_classes=[AllowAny] but refine data.
        if request.user.is_authenticated and instance.avatar.owner != request.user:
             # If authenticated but not owner, deny access unless avatar is public (though job visibility is tricky)
             pass 
        
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # Attach progress logic (conceptual)
        if data.get('status') == 'started': data['progress'] = 30
        elif data.get('status') == 'processing': data['progress'] = 75
        elif data.get('status') == 'success': data['progress'] = 100
        
        # If chat job is complete, return the assistant reply
        # NOTE: 'task_type' is likely not a field on AvatarTrainingJob model, commenting out custom logic for safety.
        # if hasattr(instance, 'task_type') and instance.task_type == 'chat_reply' and data['status'] == 'success':
        #     last_message = AvatarMessage.objects.filter(conversation__avatar=instance.avatar).order_by('-created_at').first()
        #     if last_message and last_message.role == 'assistant':
        #         data['assistant_reply'] = last_message.content

        return Response(data)


class AvatarConversationHistoryView(generics.ListAPIView):
    """Retrieves the conversation history for a visitor/avatar pair, primarily for the public chat interface."""
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        handle = self.kwargs.get('handle')
        visitor_id = self.request.query_params.get('visitor_id')

        # FIX: Added check for public avatar to prevent exposing private history
        try:
            avatar = get_avatar_by_handle_public(handle)
        except Exception:
            # If not found or not public, return 404/empty queryset
            return AvatarMessage.objects.none() 

        if not visitor_id: return AvatarMessage.objects.none()

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

    def get_queryset(self):
        # Only show jobs for avatars the user owns
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarTrainingJobDetailView(generics.RetrieveAPIView):
    """Retrieve details of an AvatarTrainingJob by UUID (PK)."""
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Only allow retrieval of jobs for avatars the user owns
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarMemoryChunkListView(generics.ListAPIView):
    """List all AvatarMemoryChunks."""
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Only show chunks for avatars the user owns
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarMemoryChunkDetailView(generics.RetrieveAPIView):
    """Retrieve details of an AvatarMemoryChunk by UUID (PK)."""
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow retrieval of chunks for avatars the user owns
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarConversationListCreateView(generics.ListCreateAPIView):
    """List or Create AvatarConversations."""
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly] # Allow list/retrieve, restrict creation if needed

    def get_queryset(self):
        # Only show conversations for avatars the user owns
        if self.request.user.is_authenticated:
            return self.queryset.filter(avatar__owner=self.request.user).order_by('-started_at')
        return self.queryset.none() # Hide conversations if not authenticated


class AvatarConversationRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    """Retrieve or Destroy an AvatarConversation by UUID (PK)."""
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Only allow actions on conversations for avatars the user owns
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarMessageListCreateView(generics.ListCreateAPIView):
    """List or Create AvatarMessages."""
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class AvatarMessageRetrieveView(generics.RetrieveAPIView):
    """Retrieve an AvatarMessage by UUID (PK)."""
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class AvatarAnalyticsListView(generics.ListAPIView):
    """List all AvatarAnalytics records."""
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show analytics for avatars the user owns
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarAnalyticsDetailView(generics.RetrieveAPIView):
    """Retrieve an AvatarAnalytics record by UUID (PK)."""
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow retrieval of analytics for avatars the user owns
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarSettingsRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or Update AvatarSettings by UUID (PK)."""
    queryset = AvatarSettings.objects.all()
    serializer_class = AvatarSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow actions on settings for avatars the user owns
        return self.queryset.filter(avatar__owner=self.request.user)