from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
from decouple import config

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whisprai.settings')

app = Celery('whisprai')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
app.conf.include = [
    'whisone.tasks.send_reminders',
    'whisone.tasks.daily_summary',
]


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
    result_backend= config("REDIS_URL", default="redis://127.0.0.1:6379/0"),
    result_expires=3600,  # Expire results after 1hr
    
    # Beat: Use DB for dynamic schedules
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler',
    beat_timezone='UTC',  # Align with your AutomationService
)


app.conf.beat_schedule = {
    'check-reminders-every-minute': {
        'task': 'whisone.tasks.send_reminders.check_and_send_reminders',
        'schedule': 60.0,  # every minute
    },
    "daily-summary-9am": {
        "task": "whisone.tasks.daily_summary.run_daily_summary",
        "schedule": crontab(hour=12, minute=56),  # every day at 8 AM
    }
}

# Suppress tokenizer warnings (for HF models in tasks)
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

# Debug task for testing
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')