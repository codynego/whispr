from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whisprai.settings')

app = Celery('whisprai')

# Load task-specific configurations (including time limits) from Django settings.
# Ensure your settings.py has:
# CELERY_TASK_TIME_LIMIT = 600  # Hard limit: 10 minutes
# CELERY_TASK_SOFT_TIME_LIMIT = 540  # Soft limit: 9 minutes
# CELERY_WORKER_CONCURRENCY = 1  # Reduce for low-spec instances to avoid overload
# CELERY_ACKS_LATE = True  # Acknowledge tasks after completion for reliability
app.config_from_object('django.conf:settings', namespace='CELERY')

# Override or set defaults here if not in settings.py (fallback for quick testing)
app.conf.update(
    task_time_limit=600,  # Hard timeout: Kill after 10min
    task_soft_time_limit=540,  # Soft timeout: Warn after 9min, allow graceful exit
    worker_concurrency=1,  # Limit to 1 worker process on 1vCPU instance
    worker_prefetch_multiplier=1,  # Avoid prefetching too many tasks
    task_acks_late=True,  # Requeue if worker crashes mid-task
    task_reject_on_worker_lost=True,  # Reject and requeue lost tasks
)

app.autodiscover_tasks()

# Beat schedule for periodic syncs – every 2 minutes as before.
# Consider staggering if multiple users to avoid API rate limits.
app.conf.beat_schedule = {
    'sync-messages-every-2-minutes': {
        'task': 'unified.tasks.common_tasks.periodic_channel_sync',
        'schedule': crontab(minute='*/2'),
    },
}

# Suppress Hugging Face tokenizers warning by disabling parallelism early.
# Set this env var in your startup script: export TOKENIZERS_PARALLELISM=false
# Or add here if needed (but env var is preferred for workers).
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')