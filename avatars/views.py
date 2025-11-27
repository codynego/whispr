# whisone/avatars/views.py
from rest_framework import generics, permissions
from .models import (
    Avatar,
    AvatarSource,
    AvatarTrainingJob,
    AvatarMemoryChunk,
    AvatarConversation,
    AvatarMessage,
    AvatarAnalytics,
    AvatarSettings,
)
from .serializers import (
    AvatarSerializer,
    AvatarSourceSerializer,
    AvatarTrainingJobSerializer,
    AvatarMemoryChunkSerializer,
    AvatarConversationSerializer,
    AvatarMessageSerializer,
    AvatarAnalyticsSerializer,
    AvatarSettingsSerializer,
)


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .tasks import train_avatar_task
from avatars.services.chat_engine import generate_avatar_reply 




# ----------------------------
# Avatar Views
# ----------------------------

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


# ----------------------------
# Avatar Source Views
# ----------------------------

class AvatarSourceListCreateView(generics.ListCreateAPIView):
    queryset = AvatarSource.objects.all()
    serializer_class = AvatarSourceSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarSourceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AvatarSource.objects.all()
    serializer_class = AvatarSourceSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----------------------------
# Avatar Training Job Views
# ----------------------------

class AvatarTrainingJobListView(generics.ListAPIView):
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarTrainingJobDetailView(generics.RetrieveAPIView):
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----------------------------
# Avatar Memory Chunk Views
# ----------------------------

class AvatarMemoryChunkListView(generics.ListAPIView):
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarMemoryChunkDetailView(generics.RetrieveAPIView):
    queryset = AvatarMemoryChunk.objects.all()
    serializer_class = AvatarMemoryChunkSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----------------------------
# Avatar Conversation & Messages
# ----------------------------

class AvatarConversationListCreateView(generics.ListCreateAPIView):
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        # visitor_id can be from session or request data
        visitor_id = self.request.session.session_key or self.request.data.get("visitor_id")
        serializer.save(visitor_id=visitor_id)


class AvatarConversationRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    queryset = AvatarConversation.objects.all()
    serializer_class = AvatarConversationSerializer
    permission_classes = [permissions.AllowAny]


class AvatarMessageListCreateView(generics.ListCreateAPIView):
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        serializer.save()


class AvatarMessageRetrieveView(generics.RetrieveAPIView):
    queryset = AvatarMessage.objects.all()
    serializer_class = AvatarMessageSerializer
    permission_classes = [permissions.AllowAny]


# ----------------------------
# Avatar Analytics
# ----------------------------

class AvatarAnalyticsListView(generics.ListAPIView):
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]


class AvatarAnalyticsDetailView(generics.RetrieveAPIView):
    queryset = AvatarAnalytics.objects.all()
    serializer_class = AvatarAnalyticsSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----------------------------
# Avatar Settings
# ----------------------------

class AvatarSettingsRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    queryset = AvatarSettings.objects.all()
    serializer_class = AvatarSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]






class AvatarChatView(APIView):
    """
    Endpoint for visitors to chat with an Avatar (sync request).
    """

    def post(self, request, handle):
        avatar = get_object_or_404(Avatar, handle=handle, trained=True)

        visitor_id = request.data.get("visitor_id") or request.session.session_key
        message_text = request.data.get("message")

        if not message_text:
            return Response(
                {"error": "Message is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ----------------------------------------------------
        # 1. Get or create an active conversation
        # ----------------------------------------------------
        conversation, created = AvatarConversation.objects.get_or_create(
            avatar=avatar,
            visitor_id=visitor_id,
            ended_at=None
        )

        # ----------------------------------------------------
        # 2. Save visitor message
        # ----------------------------------------------------
        visitor_message = AvatarMessage.objects.create(
            conversation=conversation,
            role="visitor",
            content=message_text
        )

        # ----------------------------------------------------
        # 3. Generate avatar reply — SYNC (Celery task)
        # ----------------------------------------------------
        # Runs as a blocking task → call directly for sync
        avatar_msg_id = generate_avatar_reply(
            conversation_id=str(conversation.id),
            user_message_id=str(visitor_message.id)
        )

        avatar_message = AvatarMessage.objects.get(id=avatar_msg_id)

        # ----------------------------------------------------
        # 4. Return final messages
        # ----------------------------------------------------
        return Response({
            "conversation_id": str(conversation.id),
            "avatar_reply": avatar_message.content,
            "messages": [
                {"role": visitor_message.role, "content": visitor_message.content},
                {"role": avatar_message.role, "content": avatar_message.content},
            ]
        }, status=status.HTTP_200_OK)


class AvatarTrainView(APIView):

    def post(self, request, handle):
        avatar = get_object_or_404(Avatar, handle=handle, owner=request.user)

        job = AvatarTrainingJob.objects.create(
            avatar=avatar,
            status="queued"
        )

        train_avatar_task.delay(str(job.id))

        return Response({
            "job_id": str(job.id),
            "status": job.status,
            "message": f"Training for avatar '{avatar.name}' has been queued."
        }, status=status.HTTP_201_CREATED)



class AvatarTrainingJobStatusView(generics.RetrieveAPIView):
    queryset = AvatarTrainingJob.objects.all()
    serializer_class = AvatarTrainingJobSerializer
    lookup_field = "id"
    permission_classes = [permissions.IsAuthenticated]