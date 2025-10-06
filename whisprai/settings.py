import os

# Check DJANGO_ENV environment variable
ENV = os.getenv('DJANGO_ENV', 'development').lower()

if ENV == 'production':
    from .production import *
else:
    from .development import *
