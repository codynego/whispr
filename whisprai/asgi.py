import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Set the default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "whisprai.settings")

# Initialize Django before importing anything that touches models
django_asgi_app = get_asgi_application()

# Import WebSocket routes AFTER Django initializes
from avatars.routing import websocket_urlpatterns

# Define the ASGI application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
