import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Import your project's WebSocket URL patterns
from avatars.routing import websocket_urlpatterns

# Set the default settings file for the Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whisprai.settings')

# The main ASGI callable for the server (Daphne)
# It routes incoming connections (http or websocket) to the correct handler.
application = ProtocolTypeRouter({
    # 1. Standard HTTP requests (handled by Django's regular mechanism)
    "http": get_asgi_application(),

    # 2. WebSocket connections (handled by Channels)
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})