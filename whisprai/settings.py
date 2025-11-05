from decouple import config

# Check DJANGO_ENV environment variable
ENV = config('DJANGO_ENV', 'production').lower()

if ENV == 'production':
    from .production import *
else:
    from .development import *
