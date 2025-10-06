from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whisprai.settings')

app = Celery('whisprai')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat schedule
app.conf.beat_schedule = {
    'sync-emails-every-15-minutes': {
        'task': 'emails.tasks.sync_all_emails',
        'schedule': crontab(minute='*/15'),
    },
    'check-email-importance-every-30-minutes': {
        'task': 'emails.tasks.analyze_email_importance',
        'schedule': crontab(minute='*/30'),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
