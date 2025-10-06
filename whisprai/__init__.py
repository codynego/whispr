from __future__ import absolute_import, unicode_literals
import os
from decouple import config

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)




ENV = config('DJANGO_ENV', default='development')
if ENV == 'production':
    from .production import *
else:
    from .development import *
