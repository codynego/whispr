# avatars/tasks/training.py

from celery import shared_task
from django.shortcuts import get_object_or_404
from avatars.models import AvatarTrainingJob, Avatar
from avatars.tasks.training import train_avatar


@shared_task
def train_avatar_task(job_id: str):
    """
    Celery task wrapper that loads the job + avatar
    and runs the training pipeline.
    """
    job = get_object_or_404(AvatarTrainingJob, id=job_id)
    avatar = job.avatar

    # Update job status to running
    job.status = "running"
    job.save(update_fields=["status"])

    try:
        # Run actual training logic
        train_avatar(avatar, job)

        # Job completion is handled *inside train_avatar*
        return {"job_id": job_id, "status": "completed"}

    except Exception as e:
        job.status = "error"
        job.add_log(f"Training failed: {str(e)}")
        job.save(update_fields=["status"])
        return {"job_id": job_id, "status": "error", "error": str(e)}
