# """
# Production settings for Whisone (DigitalOcean deployment)
# """

# from pathlib import Path
# from datetime import timedelta
# from decouple import config
# import dj_database_url
# import os
# import ssl

# # --- Base Paths ---
# BASE_DIR = Path(__file__).resolve().parent.parent.parent

# # --- Security ---
# SECRET_KEY = config('SECRET_KEY')
# DEBUG = True  # Set to True only for local dev

# ALLOWED_HOSTS = [
#     "whisone.app",
#     "www.whisone.app",
#     "api.whisone.app",
#     "104.248.249.124",
# ]

# CORS_ALLOWED_ORIGINS = [
#     "https://whisone.app",
#     "https://www.whisone.app",
# ]
# CORS_ALLOW_CREDENTIALS = True
# CORS_ALLOW_METHODS = [
#     'DELETE',
#     'GET',
#     'OPTIONS',
#     'PATCH',
#     'POST',
#     'PUT',
# ]
# CORS_ALLOW_HEADERS = [
#     'accept',
#     'accept-encoding',
#     'authorization',
#     'content-type',
#     'dnt',
#     'origin',
#     'user-agent',
#     'x-csrftoken',
#     'x-requested-with',
# ]

# CSRF_TRUSTED_ORIGINS = [
#     'https://whisone.app',
#     'https://www.whisone.app',
#     'https://api.whisone.app',
# ]

# # --- Celery Retries ---
# broker_connection_retry_on_startup = True
# broker_connection_max_retries = 20  # Increased for Upstash transients

# # --- Installed Apps ---
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
#     'corsheaders.middleware.CorsMiddleware',  # Must be first
#     'django.middleware.security.SecurityMiddleware',
#     'whitenoise.middleware.WhiteNoiseMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
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
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': config('DB_NAME', default='whisone'),
#         'USER': config('DB_USER', default='whisone_user'),
#         'PASSWORD': config('DB_PASSWORD', default='yourpassword'),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='5432'),
#     }
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

# # --- JWT ---
# SIMPLE_JWT = {
#     'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=60, cast=int)),
#     'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
#     'ROTATE_REFRESH_TOKENS': True,
#     'BLACKLIST_AFTER_ROTATION': True,
#     'ALGORITHM': 'HS256',
#     'SIGNING_KEY': SECRET_KEY,
#     'AUTH_HEADER_TYPES': ('Bearer',),
# }

# # --- Localization ---
# LANGUAGE_CODE = 'en-us'
# TIME_ZONE = 'Africa/Lagos'
# USE_I18N = True
# USE_TZ = True

# # --- Static & Media Files ---
# STATIC_URL = '/static/'
# STATIC_ROOT = BASE_DIR / 'staticfiles'
# MEDIA_URL = '/media/'
# MEDIA_ROOT = BASE_DIR / 'media'
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# # --- Celery / Redis (Upstash-Optimized) ---
# REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')  # Set to rediss://... in .env

# # Append SSL param if rediss:// (for Upstash self-signed certs)
# if REDIS_URL.startswith("rediss://"):
#     separator = "&" if "?" in REDIS_URL else "?"
#     REDIS_URL = f"{REDIS_URL}{separator}ssl_cert_reqs=none"

# CELERY_BROKER_URL = REDIS_URL
# CELERY_RESULT_BACKEND = REDIS_URL

# CELERY_ACCEPT_CONTENT = ["json"]
# CELERY_TASK_SERIALIZER = "json"
# CELERY_RESULT_SERIALIZER = "json"
# CELERY_TIMEZONE = "Africa/Lagos"
# CELERY_ENABLE_UTC = True
# CELERY_TASK_TRACK_STARTED = True
# CELERY_TASK_TIME_LIMIT = 30 * 60

# # Upstash-Specific: Keepalives & Retries to Prevent Idle Drops
# CELERY_BROKER_TRANSPORT_OPTIONS = {
#     'visibility_timeout': 3600,  # 1 hour
#     'socket_timeout': 30,
#     'socket_connect_timeout': 10,
#     'socket_keepalive': True,
#     'socket_keepalive_options': {3: 7200},  # Probe every 2 hours
#     'retry_policy': {
#         'interval_start': 0,
#         'interval_step': 1,
#         'max_retries': 20,
#     },
#     'ssl_cert_reqs': ssl.CERT_NONE if REDIS_URL.startswith('rediss://') else None,  # Upstash: Disable verification
# }
# CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = CELERY_BROKER_TRANSPORT_OPTIONS

# CELERY_BEAT_SCHEDULE = {
#     'sync-messages-every-2-mins': {
#         'task': 'unified.tasks.common_tasks.periodic_channel_sync',
#         'schedule': 120.0,
#     },
# }

# # --- Cache ---
# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": REDIS_URL,
#         "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
#         "KEY_PREFIX": "whisone",
#     }
# }

# # --- Email ---
# EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
# EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
# EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
# EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
# EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
# EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# # --- Third-party API Keys ---
# OPENAI_API_KEY = config('OPENAI_API_KEY', default='')
# PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
# PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
# GMAIL_CLIENT_ID = config('GMAIL_CLIENT_ID', default='')
# GMAIL_CLIENT_SECRET = config('GMAIL_CLIENT_SECRET', default='')
# DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
# WHATSAPP_API_URL = config('WHATSAPP_API_URL', default='https://graph.facebook.com/v20.0')
# WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='YOUR_PHONE_NUMBER_ID')
# WHATSAPP_ACCESS_TOKEN = config('WHATSAPP_ACCESS_TOKEN', default='YOUR_LONG_LIVED_ACCESS_TOKEN')
# WHATSAPP_VERIFY_TOKEN = config('WHATSAPP_VERIFY_TOKEN', default='YOUR_VERIFY_TOKEN')
# HUGGINGFACE_API_KEY = config('HUGGINGFACE_API_KEY', default='')
# HUGGINGFACE_SUMMARIZATION_MODEL = config('HUGGINGFACE_SUMMARIZATION_MODEL', default='facebook/bart-large-cnn') 

# # --- Swagger ---
# SWAGGER_SETTINGS = {
#     'SECURITY_DEFINITIONS': {'Bearer': {'type': 'apiKey', 'name': 'Authorization', 'in': 'header'}},
#     'USE_SESSION_AUTH': False,
# }

# # --- Security ---
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

# --- Base Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Security ---
SECRET_KEY = config("SECRET_KEY")
DEBUG = True  # Production mode

ALLOWED_HOSTS = [
    "whisone.app",
    "www.whisone.app",
    "api.whisone.app",
    "104.248.249.124",
]

# --- CORS & CSRF ---
CORS_ALLOWED_ORIGINS = [
    "https://whisone.app",
    "https://www.whisone.app",
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    "https://whisone.app",
    "https://www.whisone.app",
    "https://api.whisone.app",
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# --- Installed Apps ---
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "drf_yasg",
    "django_celery_beat",
    "django_celery_results",

    # Local apps
    "users",
    "emails",
    "whatsapp",
    "assistant",
    "billing",
    "notifications",
    "unified",
    'whisone',
    
]

# --- Middleware ---
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "whisprai.urls"

# --- Templates ---
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "whisprai.wsgi.application"

# --- Database ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="whisone"),
        "USER": config("DB_USER", default="whisone_user"),
        "PASSWORD": config("DB_PASSWORD", default="yourpassword"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        'CONN_MAX_AGE': 0,  # Disable persistent connections in workers to avoid stale ones
    }
}
# Celery-specific
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Process one task at a time to reduce DB load
CELERYD_CONCURRENCY = 2  # Lower if 1vCPU is bottleneck

# --- Authentication ---
AUTH_USER_MODEL = "users.User"

# --- REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# --- JWT ---
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("JWT_ACCESS_TOKEN_LIFETIME", default=60, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- Localization ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# --- Static & Media Files ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- Celery (Local Redis setup) ---
REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/0")

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL # Uses django_celery_results
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Africa/Lagos"
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# settings.py (or celery.py if you define CELERY_BEAT_SCHEDULE there)
import os
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {

    "check-reminders-every-minute": {
        "task": "whisone.tasks.send_reminders.check_and_send_reminders",  # update with your app path
        "schedule": 60.0,  # every 1 minute
    },
    "daily-summary-9am": {
        "task": "whisone.tasks.daily_summary.run_daily_summary",
        "schedule": crontab(hour=10, minute=00),  # every day at 8 AM
    }
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
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# --- Third-party API Keys ---
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
PAYSTACK_SECRET_KEY = config("PAYSTACK_SECRET_KEY", default="")
PAYSTACK_PUBLIC_KEY = config("PAYSTACK_PUBLIC_KEY", default="")
GMAIL_CLIENT_ID = config("GMAIL_CLIENT_ID", default="")
GMAIL_CLIENT_SECRET = config("GMAIL_CLIENT_SECRET", default="")
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")
WHATSAPP_API_URL = config("WHATSAPP_API_URL", default="https://graph.facebook.com/v20.0")
WHATSAPP_PHONE_NUMBER_ID = config("WHATSAPP_PHONE_NUMBER_ID", default="YOUR_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = config("WHATSAPP_ACCESS_TOKEN", default="YOUR_LONG_LIVED_ACCESS_TOKEN")
WHATSAPP_VERIFY_TOKEN = config("WHATSAPP_VERIFY_TOKEN", default="YOUR_VERIFY_TOKEN")
HUGGINGFACE_API_KEY = config("HUGGINGFACE_API_KEY", default="")
HUGGINGFACE_SUMMARIZATION_MODEL = config("HUGGINGFACE_SUMMARIZATION_MODEL", default="facebook/bart-large-cnn")

# --- Swagger ---
SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {"Bearer": {"type": "apiKey", "name": "Authorization", "in": "header"}},
    "USE_SESSION_AUTH": False,
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

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs/whisone.log",
            "formatter": "verbose",
        },
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "loggers": {
        "django": {"handlers": ["file", "console"], "level": "INFO", "propagate": True},
        "celery": {"handlers": ["file", "console"], "level": "INFO", "propagate": True},
    },
}

# --- Default PK ---
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
