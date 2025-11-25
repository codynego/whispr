# avatars/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/@(?P<handle>[\w-]+)/$", consumers.AvatarChatConsumer.as_asgi()),
]