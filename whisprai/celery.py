from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whisprai.settings')

app = Celery('whisprai')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Load task-specific configurations from Django settings.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Use django-celery-beat for dynamic scheduling (e.g., automations)
app.conf.update(
    # Time limits for long-running tasks (e.g., AI summaries)
    task_time_limit=600,  # Hard: Kill after 10min
    task_soft_time_limit=540,  # Soft: Warn after 9min
    
    # Worker tuning for low-spec (1vCPU)
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Results backend (for inspecting task outcomes)
    result_backend='django-db',  # Requires django-celery-results
    result_expires=3600,  # Expire results after 1hr
    
    # Beat: Use DB for dynamic schedules
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler',
    beat_timezone='UTC',  # Align with your AutomationService
)

# Static Beat schedule: Periodic syncs (stagger if multi-instance)
app.conf.beat_schedule = {
    'sync-messages-every-2-minutes': {
        'task': 'unified.tasks.common_tasks.periodic_channel_sync',
        'schedule': crontab(minute='*/2'),
    },
    # Add if needed: e.g., daily cleanup
    # 'cleanup-old-results': {
    #     'task': 'assistant.tasks.cleanup_old_automations',
    #     'schedule': crontab(hour=2, minute=0),  # 2AM UTC
    # },
}

# Suppress tokenizer warnings (for HF models in tasks)
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

# Debug task for testing
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')