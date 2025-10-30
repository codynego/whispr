
# """
# Production settings for Whisone
# """

# from pathlib import Path
# from datetime import timedelta
# from decouple import config
# import dj_database_url
# import os

# # --- Base Paths ---
# BASE_DIR = Path(__file__).resolve().parent.parent.parent

# # --- Security ---
# SECRET_KEY = config('SECRET_KEY')
# DEBUG = False
# ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='whisone.herokuapp.com,whisone.app,www.whisone.app').split(',')
# CSRF_TRUSTED_ORIGINS = config(
#     'CSRF_TRUSTED_ORIGINS',
#     default='https://whisone.herokuapp.com,https://whisone.app,https://www.whisone.app,https://whisone.vercel.app'
# ).split(',')

# INSTALLED_APPS = [
#     'django.contrib.admin',
#     'django.contrib.auth',
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',
#     'django.contrib.messages',
#     'django.contrib.staticfiles',

#     # Third-party
#     'rest_framework',
#     'rest_framework_simplejwt',
#     'corsheaders',
#     'drf_yasg',
#     'django_celery_beat',
#     'django_celery_results',

#     # Local apps
#     'users',
#     'emails',
#     'whatsapp',
#     'assistant',
#     'billing',
#     'notifications',
#     'unified',
# ]


# # --- Middleware ---
# MIDDLEWARE = [
#     'django.middleware.security.SecurityMiddleware',
#     'whitenoise.middleware.WhiteNoiseMiddleware',  # ✅ add this for static files on Heroku
#     'django.middleware.http.ConditionalGetMiddleware',
#     'corsheaders.middleware.CorsMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
# ]

# ROOT_URLCONF = 'whisprai.urls'

# # --- Templates ---
# TEMPLATES = [
#     {
#         'BACKEND': 'django.template.backends.django.DjangoTemplates',
#         'DIRS': [BASE_DIR / 'templates'],
#         'APP_DIRS': True,
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.debug',
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#             ],
#         },
#     },
# ]

# WSGI_APPLICATION = 'whisprai.wsgi.application'

# # --- Database ---
# DATABASES = {
#     'default': dj_database_url.config(
#         default=config('DATABASE_URL', default='postgres://user:password@localhost:5432/whisone'),
#         conn_max_age=600,
#         ssl_require=True
#     )
# }

# # --- Authentication ---
# AUTH_USER_MODEL = 'users.User'

# # --- REST Framework ---
# REST_FRAMEWORK = {
#     'DEFAULT_AUTHENTICATION_CLASSES': [
#         'rest_framework_simplejwt.authentication.JWTAuthentication',
#     ],
#     'DEFAULT_PERMISSION_CLASSES': [
#         'rest_framework.permissions.IsAuthenticated',
#     ],
#     'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
#     'PAGE_SIZE': 20,
# }

# # --- JWT Authentication ---
# SIMPLE_JWT = {
#     'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=60, cast=int)),
#     'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
#     'ROTATE_REFRESH_TOKENS': True,
#     'BLACKLIST_AFTER_ROTATION': True,
#     'ALGORITHM': 'HS256',
#     'SIGNING_KEY': SECRET_KEY,
#     'AUTH_HEADER_TYPES': ('Bearer',),
# }

# # --- Internationalization ---
# LANGUAGE_CODE = 'en-us'
# TIME_ZONE = 'Africa/Lagos'
# USE_I18N = True
# USE_TZ = True

# # --- Static & Media Files ---
# STATIC_URL = '/static/'
# STATIC_ROOT = BASE_DIR / 'staticfiles'
# MEDIA_URL = '/media/'
# MEDIA_ROOT = BASE_DIR / 'media'

# # ✅ Use Whitenoise compressed storage for production
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# # --- CORS ---
# CORS_ALLOWED_ORIGINS = config(
#     'CORS_ALLOWED_ORIGINS',
#     default='https://whisone.app,https://www.whisone.app,https://whisone.vercel.app'
# ).split(',')
# CORS_ALLOW_CREDENTIALS = True

# # --- Celery / Redis ---
# CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
# CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')


# import ssl

# CELERY_ACCEPT_CONTENT = ["json"]
# CELERY_TASK_SERIALIZER = "json"
# CELERY_RESULT_SERIALIZER = "json"
# CELERY_TIMEZONE = "Africa/Lagos"
# CELERY_ENABLE_UTC = True

# CELERY_TASK_TRACK_STARTED = True
# CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# REDIS_URL = config("REDIS_URL", "redis://localhost:6379")
# REDIS_SSL = config("REDIS_SSL", "False").lower() == "true"

# # Add ssl_cert_reqs parameter to the URL if using rediss://
# if REDIS_URL.startswith("rediss://"):
#     # Check if the URL already has parameters
#     separator = "&" if "?" in REDIS_URL else "?"
#     REDIS_URL = f"{REDIS_URL}{separator}ssl_cert_reqs=none"

# CELERY_BROKER_URL = REDIS_URL
# CELERY_RESULT_BACKEND = REDIS_URL

# # Configure SSL for Celery if using rediss://
# if REDIS_URL.startswith("rediss://"):
#     CELERY_BROKER_USE_SSL = {
#         "ssl_cert_reqs": ssl.CERT_NONE
#     }
#     CELERY_RESULT_BACKEND_USE_SSL = {
#         "ssl_cert_reqs": ssl.CERT_NONE
#     }

# # Celery Beat Scheduler
# CELERY_BEAT_SCHEDULE = {
#     'sync-emails-every-10-mins': {
#         'task': 'emails.tasks.periodic_email_sync',
#         'schedule': 600.0,  # every 10 minutes
#     },
# }

# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": REDIS_URL,  # Now includes ssl_cert_reqs in the URL
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#         },
#         "KEY_PREFIX": "whisprai",
#     }
# }

# # --- Email ---
# EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
# EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
# EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
# EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
# EMAIL_HOST_USER = config('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')

# # --- Third-party API Keys ---
# OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
# PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
# PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')

# # --- WhatsApp Cloud API ---
# WHATSAPP_API_URL = config('WHATSAPP_API_URL', default='https://graph.facebook.com/v18.0')
# WHATSAPP_ACCESS_TOKEN = config('WHATSAPP_ACCESS_TOKEN', default='')
# WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='')
# WHATSAPP_VERIFY_TOKEN = config('WHATSAPP_VERIFY_TOKEN', default='')
# GEMINI_API_KEY = config('GEMINI_API_KEY', default='')

# # --- Swagger ---
# SWAGGER_SETTINGS = {
#     'SECURITY_DEFINITIONS': {
#         'Bearer': {'type': 'apiKey', 'name': 'Authorization', 'in': 'header'}
#     },
#     'USE_SESSION_AUTH': False,
# }

# # --- Security Hardening ---
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_BROWSER_XSS_FILTER = True
# SECURE_CONTENT_TYPE_NOSNIFF = True

# # --- Default PK ---
# DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



"""
Production settings for Whisone (DigitalOcean deployment)
"""

from pathlib import Path
from datetime import timedelta
from decouple import config
import dj_database_url
import os
import ssl

# --- Base Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Security ---
SECRET_KEY = config('SECRET_KEY')
DEBUG = False

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='whisone.app,www.whisone.app,api.whisone.app,localhost,127.0.0.1'
).split(',')

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://whisone.app,https://www.whisone.app,https://api.whisone.app'
).split(',')

broker_connection_retry_on_startup = True
broker_connection_max_retries = 5

# --- Installed Apps ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_yasg',
    'django_celery_beat',
    'django_celery_results',

    # Local apps
    'users',
    'emails',
    'whatsapp',
    'assistant',
    'billing',
    'notifications',
    'unified',
]

# --- Middleware ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # still useful even with Nginx
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'whisprai.urls'

# --- Templates ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'whisprai.wsgi.application'

# --- Database ---
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='postgres://whisone_user:your_secure_password@localhost:5432/whisone_db'),
        conn_max_age=600,
        ssl_require=False  # ❌ Disable SSL since it's local
    )
}

# --- Authentication ---
AUTH_USER_MODEL = 'users.User'

# --- REST Framework ---
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# --- JWT ---
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# --- Localization ---
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

# --- Static & Media Files ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Use Whitenoise for Django-served static (Gunicorn)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- CORS ---
CORS_ALLOWED_ORIGINS = [
    'https://whisone.app,https://www.whisone.app,https://api.whisone.app'
]
CORS_ALLOW_CREDENTIALS = True

# --- Celery / Redis ---
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Lagos"
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

CELERY_BEAT_SCHEDULE = {
    'sync-emails-every-10-mins': {
        'task': 'emails.tasks.periodic_email_sync',
        'schedule': 600.0,
    },
}

# --- Cache ---
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "whisone",
    }
}

# --- Email ---
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# --- Third-party API Keys ---
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
WHATSAPP_API_URL = config('WHATSAPP_API_URL', default='https://graph.facebook.com/v18.0')
WHATSAPP_ACCESS_TOKEN = config('WHATSAPP_ACCESS_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='')
WHATSAPP_VERIFY_TOKEN = config('WHATSAPP_VERIFY_TOKEN', default='')
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')

# --- Swagger ---
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {'Bearer': {'type': 'apiKey', 'name': 'Authorization', 'in': 'header'}},
    'USE_SESSION_AUTH': False,
}

# --- Security ---
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Default PK ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
