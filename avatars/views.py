import uuid
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
# Removed: from rest_framework_extensions.mixins import CacheResponseMixin
from celery.result import AsyncResult
from uuid import UUID

# Import your models, serializers, tasks, and services
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
from avatars.tasks import train_avatar_task 
from avatars.services.chat_engine import generate_avatar_reply
from avatars.services.persona_polisher import polish_persona

# --- Caching Constants ---
PUBLIC_AVATAR_CACHE_TTL = 60 * 5  # 5 minutes
OWNER_CONFIG_CACHE_TTL = 60 * 1  # 1 minute

# --- Helper Functions (Unchanged) ---
def get_avatar_by_handle_and_owner(handle, user):
    """Retrieves an Avatar by handle, ensuring the user is the owner."""
    return get_object_or_404(Avatar, handle=handle, owner=user)

def get_avatar_by_handle_public(handle):
    """Retrieves an Avatar by handle only if its settings mark it as public."""
    return get_object_or_404(
        Avatar.objects.select_related('settings'), 
        handle=handle, 
        settings__visibility='public'
    )

# ----------------------------------------------------------------------
# 1. NEW HANDLE-BASED CONVENIENCE VIEWS (Configuration UI)
# ----------------------------------------------------------------------

# @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL), name='dispatch') works for the entire view
class AvatarRetrieveByHandleView(generics.RetrieveAPIView):
    """Retrieves Avatar details by handle. Cached for OWNER."""
    serializer_class = AvatarSerializer
    permission_classes = [permissions.IsAuthenticated] 

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        handle = self.kwargs.get('handle')
        return get_avatar_by_handle_and_owner(handle, self.request.user)

class AvatarSettingsByHandleView(generics.RetrieveUpdateAPIView):
    """Allows retrieval (cached) and update of AvatarSettings."""
    serializer_class = AvatarSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        handle = self.kwargs.get('handle')
        avatar = get_avatar_by_handle_and_owner(handle, self.request.user)
        settings, created = AvatarSettings.objects.get_or_create(
            avatar=avatar,
            defaults={'avatar': avatar}
        )
        return settings

class AvatarAnalyticsByHandleView(generics.RetrieveAPIView):
    """Retrieve AvatarAnalytics via the Avatar handle. Cached."""
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        handle = self.kwargs.get('handle')
        avatar = get_avatar_by_handle_and_owner(handle, self.request.user)
        analytics, created = AvatarAnalytics.objects.get_or_create(
            avatar=avatar,
        )
        return analytics

class AvatarSourceListCreateView(generics.ListCreateAPIView):
    """List Avatar Sources (cached) or replace them (no caching on POST)."""
    serializer_class = AvatarSourceSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        avatar_handle = self.kwargs["handle"]
        avatar = get_object_or_404(Avatar, handle=avatar_handle)
        return AvatarSource.objects.filter(avatar=avatar)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        avatar_handle = self.kwargs["handle"]
        context["avatar"] = get_object_or_404(Avatar, handle=avatar_handle)
        return context

    def create(self, request, *args, **kwargs):
        avatar = self.get_serializer_context()["avatar"]
        
        AvatarSource.objects.filter(avatar=avatar).delete()
        
        serializer = self.get_serializer(
            data=request.data,
            many=True,
            context=self.get_serializer_context()
        )
        
        if not serializer.is_valid():
            print("Validation errors:", serializer.errors)  # ADD THIS
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
# --- Public Retrieval View ---

@method_decorator(cache_page(PUBLIC_AVATAR_CACHE_TTL), name='dispatch')
class AvatarRetrievePublicView(generics.RetrieveAPIView):
    """
    Allows public retrieval of Avatar details by handle. Highly cached.
    """
    serializer_class = AvatarSerializer
    permission_classes = [permissions.AllowAny] 
    
    def get_object(self):
        handle = self.kwargs.get('handle')
        return get_avatar_by_handle_public(handle) 

# ----------------------------------------------------------------------
# 2. CHAT, TRAINING, AND HISTORY VIEWS (No Caching on POST/Polling)
# ----------------------------------------------------------------------

class AvatarChatView(APIView):
    """Endpoint for visitors to chat with an Avatar (Async request)."""
    permission_classes = [permissions.AllowAny]

    def post(self, request, handle):
        try:
            avatar = get_avatar_by_handle_public(handle)
        except Exception:
            return Response({"error": "Avatar not found or not public."}, status=status.HTTP_404_NOT_FOUND)

        # Ensure session exists
        if not request.session.session_key:
            request.session.save()
        visitor_id = request.data.get("visitor_id") or request.session.session_key
        message_text = request.data.get("message")

        if not message_text or not visitor_id:
            return Response({"error": "Message and visitor_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Track whether user is logged in
        user = request.user if request.user.is_authenticated else None
        print("user", user, request.user)

        # Create or get conversation
        conversation, _ = AvatarConversation.objects.get_or_create(
            avatar=avatar,
            visitor_id=visitor_id,
            ended_at=None,
            defaults={"user": user, 'prompted_login': False}
        )

        # If user is authenticated but conversation had no user, assign
        if user and conversation.user is None:
            conversation.user = user
            conversation.save()

        # Optionally flag for login prompt if visitor is unauthenticated
        prompted_login = False
        if not user:
            prompted_login = True
            conversation.prompted_login = True
            conversation.save()

        # Save visitor message
        visitor_message = AvatarMessage.objects.create(
            conversation=conversation, role="visitor", content=message_text
        )

        # Trigger async response generation
        task_id = generate_avatar_reply.delay(
            conversation_id=str(conversation.id),
            user_message_id=str(visitor_message.id)
        )

        return Response({
            "conversation_id": str(conversation.id),
            "task_id": str(task_id),
            "prompted_login": prompted_login
        }, status=status.HTTP_202_ACCEPTED)


class AvatarTrainView(APIView):
    """Triggers the asynchronous Celery training task for an Avatar."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, handle):
        # ... (implementation omitted for brevity, no changes needed for caching)
        avatar = get_avatar_by_handle_and_owner(handle, request.user)

        job = AvatarTrainingJob.objects.create(
            avatar=avatar, status="queued"
        )

        train_avatar_task.delay(str(job.id))

        return Response({
            "job_id": str(job.id), "status": job.status,
            "message": f"Training for avatar '{avatar.name}' has been queued."
        }, status=status.HTTP_201_CREATED)

class AvatarTrainingJobStatusView(generics.RetrieveAPIView):
    """Retrieves the status of a training job. No caching (polling endpoint)."""
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    lookup_field = "id" 
    permission_classes = [permissions.IsAuthenticated] 
    
    def retrieve(self, request, *args, **kwargs):
        # ... (implementation omitted for brevity, no changes needed for caching)
        try:
            instance = self.get_object()
        except AvatarTrainingJob.DoesNotExist:
            return Response({"detail": "Training job not found."}, status=404)

        serializer = self.get_serializer(instance)
        data = serializer.data
        status_key = data.get('status', 'failure').lower()
        
        if status_key == 'queued':
            progress = 0
        elif status_key == 'running':
            progress = 10
        elif status_key == 'processing':
            progress = data.get('progress', 50) 
        elif status_key == 'completed':
            progress = 100
        elif status_key in ('error', 'failure'):
            progress = 0
        else:
            progress = 0
            status_key = 'error' 

        response_data = {
            "status": status_key, 
            "progress": progress,
            "logs": data.get('logs') if status_key == 'error' else None,
        }

        return Response(response_data)


@method_decorator(cache_page(PUBLIC_AVATAR_CACHE_TTL), name='dispatch')
class AvatarConversationHistoryView(generics.ListAPIView):
    """Retrieves the conversation history. Cached (depends on handle/visitor_id)."""
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        handle = self.kwargs.get('handle')
        visitor_id = self.request.query_params.get('visitor_id')

        try:
            avatar = get_avatar_by_handle_public(handle)
        except Exception:
            return AvatarMessage.objects.none() 

        if not visitor_id: return AvatarMessage.objects.none()

        conversation = AvatarConversation.objects.filter(
            avatar=avatar, visitor_id=visitor_id
        ).order_by('-started_at').first()

        if not conversation: return AvatarMessage.objects.none()

        return AvatarMessage.objects.filter(conversation=conversation).order_by('created_at')


class AvatarConversationTakeoverView(APIView):
    """Allows the Avatar owner to take over a live conversation by ID. No caching (write action)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        # ... (implementation omitted for brevity, no changes needed for caching)
        conversation = get_object_or_404(AvatarConversation, pk=pk)
        
        if conversation.avatar.owner != request.user:
            return Response({"error": "You do not own this conversation's avatar."}, status=status.HTTP_403_FORBIDDEN)

        if conversation.taken_over_by_owner:
             return Response({"message": "Conversation already under human control."}, status=status.HTTP_200_OK)

        conversation.taken_over_by_owner = True
        conversation.save(update_fields=['taken_over_by_owner'])

        AvatarMessage.objects.create(
            conversation=conversation, role="owner", content=f"Human owner has taken over the chat. 👋"
        )

        return Response({"status": "takeover_active"}, status=status.HTTP_200_OK)

# ----------------------------------------------------------------------
# 3. ORIGINAL UUID-BASED VIEWS (Standard CRUD operations)
# Replaced CacheResponseMixin with @method_decorator(cache_page(...))
# ----------------------------------------------------------------------

class AvatarListCreateView(generics.ListCreateAPIView):
    """List Avatars owned by the current user. List is cached."""
    queryset = Avatar.objects.all()
    serializer_class = AvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_create(self, serializer):
        avatar = serializer.save(owner=self.request.user)
        if avatar.persona_prompt:
            polished = polish_persona(f"persona_prompt: {avatar.persona_prompt} + name: {avatar.name}")
            avatar.persona_prompt = polished
            avatar.save()


class AvatarRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve (cached), Update/Destroy (no cache) an Avatar by UUID."""
    queryset = Avatar.objects.all()
    serializer_class = AvatarSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(owner=self.request.user)

    def perform_update(self, serializer):
        avatar = serializer.save()
        if avatar.persona_prompt:
            polished = polish_persona(f"persona_prompt: {avatar.persona_prompt} + name: {avatar.name}")
            avatar.persona_prompt = polished
            avatar.save()


class AvatarSourceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve (cached), Update/Destroy (no cache) an AvatarSource by UUID (PK)."""
    queryset = AvatarSource.objects.all()
    serializer_class = AvatarSourceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AvatarTrainingJobListView(generics.ListAPIView):
    """List all AvatarTrainingJobs. List is cached."""
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarTrainingJobDetailView(generics.RetrieveAPIView):
    """Retrieve details of an AvatarTrainingJob by UUID (PK). Retrieve is cached."""
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarMemoryChunkListView(generics.ListAPIView):
    """List all AvatarMemoryChunks. List is cached."""
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarMemoryChunkDetailView(generics.RetrieveAPIView):
    """Retrieve details of an AvatarMemoryChunk by UUID (PK). Retrieve is cached."""
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarConversationListCreateView(generics.ListCreateAPIView):
    """List or Create AvatarConversations. List is cached for owner."""
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return self.queryset.filter(avatar__owner=self.request.user).order_by('-started_at')
        return self.queryset.none()


class AvatarConversationRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    """Retrieve or Destroy an AvatarConversation by UUID (PK). Retrieve is cached."""
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarMessageListCreateView(generics.ListCreateAPIView):
    """List or Create AvatarMessages. List is not cached (high volume/rapid change)."""
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class AvatarMessageRetrieveView(generics.RetrieveAPIView):
    """Retrieve an AvatarMessage by UUID (PK). Retrieve is cached."""
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AvatarAnalyticsListView(generics.ListAPIView):
    """List all AvatarAnalytics records. List is cached."""
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarAnalyticsDetailView(generics.RetrieveAPIView):
    """Retrieve an AvatarAnalytics record by UUID (PK). Retrieve is cached."""
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarSettingsRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve (cached) or Update (no cache) AvatarSettings by UUID (PK)."""
    queryset = AvatarSettings.objects.all()
    serializer_class = AvatarSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(OWNER_CONFIG_CACHE_TTL))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.queryset.filter(avatar__owner=self.request.user)


class AvatarChatTaskStatusView(APIView):
    """Endpoint for the frontend to poll the status and result of a chat generation task. No caching."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, task_id):
        # ... (implementation omitted for brevity, no changes needed for caching)
        task_id_str = str(task_id)
        task_result = AsyncResult(task_id_str)

        if task_result.successful():
            try:
                message_id = task_result.result 
                assistant_message = AvatarMessage.objects.get(id=message_id)
                
                return Response({
                    "status": "SUCCESS",
                    "assistant_reply": assistant_message.content,
                    "message_id": str(assistant_message.id),
                    "created_at": assistant_message.created_at,
                }, status=status.HTTP_200_OK)
            except Exception:
                return Response({
                    "status": "FAILURE",
                    "error": "Task succeeded, but message record not found.",
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        elif task_result.failed():
            return Response({
                "status": "FAILURE",
                "error": str(task_result.result),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        else:
            return Response({
                "status": task_result.status,
            }, status=status.HTTP_200_OK)