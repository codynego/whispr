import uuid
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Avatar, AvatarConversation, AvatarMessage
from .serializers import AvatarMessageSerializer
  # RAG + streaming


class AvatarChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.handle = self.scope["url_route"]["kwargs"]["handle"]

        # Resolve avatar + access control
        self.avatar = await self.get_avatar()
        if not self.avatar:
            await self.close(code=4404)  # Not Found
            return

        if self.avatar.visibility != "public":
            # Add protected/private logic later (e.g. ?code=xyz)
            await self.close(code=4403)  # Forbidden
            return

        # Visitor identification
        self.visitor_id = self.scope["session"].setdefault("visitor_id", str(uuid.uuid4()))
        self.scope["session"].save()

        # Conversation
        self.conversation = await self.get_or_create_conversation()
        self.room_group_name = f"chat_{self.conversation.id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        # Send welcome + full history
        await self.send_welcome_message()
        await self.send_conversation_history()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        # Auto-end inactive conversations after 30 mins
        if hasattr(self, "conversation") and self.conversation and not self.conversation.ended_at:
            await self.mark_conversation_ended_if_inactive()

    # ──────────────────────────────────────────────────────────────────────
    # Incoming messages from visitor
    # ──────────────────────────────────────────────────────────────────────
    async def receive_json(self, content, **kwargs):
        from avatars.services.chat_engine import generate_streaming_response
        msg_type = content.get("type")

        if msg_type == "chat.message":
            text = content.get("message", "").strip()
            if not text:
                return

            message = await self.save_message(role="visitor", content=text)

            # Broadcast visitor message instantly
            await self.broadcast_message(message)

            # Trigger streaming AI response (RAG + token-by-token)
            generate_streaming_response.delay(
                conversation_id=str(self.conversation.id),
                user_message_id=str(message.id)
            )

        elif msg_type == "visitor.info":
            await self.update_visitor_info(
                name=content.get("name"),
                email=content.get("email")
            )

        elif msg_type == "typing.start":
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "visitor.typing", "typing": True}
            )

        elif msg_type == "typing.stop":
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "visitor.typing", "typing": False}
            )

    # ──────────────────────────────────────────────────────────────────────
    # Broadcast events (called from tasks.py or owner dashboard)
    # ──────────────────────────────────────────────────────────────────────
    async def chat_message(self, event):
        await self.send_json({
            "type": "chat.message",
            "message": event["message"]  # already serialized with is_streaming, etc.
        })

    async def visitor_typing(self, event):
        await self.send_json({
            "type": "visitor.typing",
            "typing": event["typing"]
        })

    # ──────────────────────────────────────────────────────────────────────
    # DB Helpers (async-safe)
    # ──────────────────────────────────────────────────────────────────────
    @database_sync_to_async
    def get_avatar(self):
        try:
            return Avatar.objects.get(handle=self.handle, is_deleted=False)
        except Avatar.DoesNotExist:
            return None

    @database_sync_to_async
    def get_or_create_conversation(self):
        convo, created = AvatarConversation.objects.get_or_create(
            avatar=self.avatar,
            visitor_id=self.visitor_id,
            defaults={
                "started_at": timezone.now(),
                "last_activity_at": timezone.now(),
            }
        )
        if not created:
            convo.last_activity_at = timezone.now()
            convo.save(update_fields=["last_activity_at"])
        return convo

    @database_sync_to_async
    def save_message(self, role: str, content: str, model_used: str = None):
        return AvatarMessage.objects.create(
            conversation=self.conversation,
            role=role,
            content=content,
            model_used=model_used,
        )

    @database_sync_to_async
    def update_visitor_info(self, name=None, email=None):
        updated = False
        if name and not self.conversation.visitor_name:
            self.conversation.visitor_name = name
            updated = True
        if email and not self.conversation.visitor_email:
            self.conversation.visitor_email = email
            updated = True
        if updated:
            self.conversation.save()

    @database_sync_to_async
    def mark_conversation_ended_if_inactive(self):
        if (timezone.now() - self.conversation.last_activity_at).total_seconds() > 1800:  # 30 min
            self.conversation.ended_at = timezone.now()
            self.conversation.save()

    # ──────────────────────────────────────────────────────────────────────
    # Initial chat load
    # ──────────────────────────────────────────────────────────────────────
    async def send_welcome_message(self):
        if self.avatar.welcome_message:
            welcome = {
                "id": str(uuid.uuid4()),
                "role": "avatar",
                "content": self.avatar.welcome_message,
                "created_at": timezone.now().isoformat(),
            }
            await self.send_json({
                "type": "chat.message",
                "message": welcome
            })

    async def send_conversation_history(self):
        history = await self.get_history()
        for msg in history:
            await self.send_json({
                "type": "chat.message",
                "message": AvatarMessageSerializer(msg).data
            })

    @database_sync_to_async
    def get_history(self):
        return list(
            AvatarMessage.objects.filter(conversation=self.conversation)
            .order_by("created_at")
            .all()
        )

    # ──────────────────────────────────────────────────────────────────────
    # Helper: broadcast full message
    # ──────────────────────────────────────────────────────────────────────
    async def broadcast_message(self, message_obj):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "message": AvatarMessageSerializer(message_obj).data,
            }
        )