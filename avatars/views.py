# avatars/views.py
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404
from django.utils import timezone

from avatars.models import Avatar, AvatarConversation, AvatarTrainingJob
from avatars.serializers import (
    AvatarListSerializer,
    AvatarDetailSerializer,
    AvatarCreateSerializer,
    AvatarUpdateSerializer,
    AvatarPublicSerializer,
    AvatarConversationSerializer,
    AvatarTrainingJobSerializer,
)
from avatars.tasks.training import run_avatar_training  # ← your final training task


# ===================================================================
# OWNER-FACING VIEWS
# ===================================================================

class AvatarListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AvatarListSerializer

    def get_queryset(self):
        return Avatar.objects.filter(owner=self.request.user, is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class AvatarDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return Avatar.objects.filter(owner=self.request.user, is_deleted=False)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return AvatarUpdateSerializer
        return AvatarDetailSerializer

    def perform_destroy(self, instance):
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ===================================================================
# PUBLIC AVATAR PAGE (@handle)
# ===================================================================

class AvatarPublicDetailView(generics.RetrieveAPIView):
    serializer_class = AvatarPublicSerializer
    lookup_field = "handle"
    lookup_url_kwarg = "handle"

    def get_object(self):
        handle = self.kwargs["handle"]
        code = self.request.query_params.get("code", "")

        avatar = get_object_or_404(Avatar.objects.filter(is_deleted=False), handle=handle)

        if avatar.visibility == "public":
            return avatar
        if avatar.visibility == "protected" and avatar.protected_code == code:
            return avatar
        if avatar.visibility == "private":
            raise PermissionDenied("This avatar is private.")
        raise NotFound("Invalid access code.")

# ===================================================================
# CONVERSATIONS & TRAINING JOBS
# ===================================================================

class AvatarConversationListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AvatarConversationSerializer

    def get_queryset(self):
        avatar = get_object_or_404(
            Avatar, id=self.kwargs["avatar_id"], owner=self.request.user, is_deleted=False
        )
        return avatar.conversations.filter(is_deleted=False).order_by("-started_at")


class AvatarTrainingJobListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AvatarTrainingJobSerializer

    def get_queryset(self):
        avatar = get_object_or_404(
            Avatar, id=self.kwargs["avatar_id"], owner=self.request.user
        )
        return avatar.training_jobs.order_by("-created_at")


# ===================================================================
# TRIGGER TRAINING — CLEAN, DRF-STYLE (no ViewSet, no csrf_exempt)
# ===================================================================

class AvatarTrainView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        avatar = get_object_or_404(
            Avatar,
            id=id,
            owner=request.user,
            is_deleted=False
        )

        # Prevent training spam
        recent_job = avatar.training_jobs.filter(
            created_at__gte=timezone.now() - timezone.timedelta(minutes=3)
        ).first()

        if recent_job and recent_job.status in ["queued", "running"]:
            return Response(
                {
                    "error": "Training already in progress. Please wait.",
                    "current_job": {
                        "id": str(recent_job.id),
                        "status": recent_job.status
                    }
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Create new job
        job = AvatarTrainingJob.objects.create(
            avatar=avatar,
            status="queued"
        )

        # Fire Celery task
        run_avatar_training.delay(str(job.id))

        return Response(
            {
                "success": True,
                "job_id": str(job.id),
                "status": "queued",
                "message": "Training started! We'll notify you when it's done."
            },
            status=status.HTTP_202_ACCEPTED
        )


# Optional: Get latest training status
class AvatarTrainingStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        avatar = get_object_or_404(Avatar, id=id, owner=request.user)
        job = avatar.training_jobs.order_by("-created_at").first()

        if not job:
            return Response({"status": "never_trained"})

        return Response({
            "job_id": str(job.id),
            "status": job.status,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "logs": (job.logs or "").strip().split("\n")[-15:] if job.logs else []
        })