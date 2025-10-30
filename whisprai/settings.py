import os

# Check DJANGO_ENV environment variable
ENV = os.getenv('DJANGO_ENV', 'production').lower()

if ENV == 'production':
    from .production import *
else:
    from .development import *
