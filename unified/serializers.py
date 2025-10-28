from rest_framework import serializers
from .models import ChannelAccount, Conversation, Message, UserRule


# ---------------- CHANNEL ACCOUNT ---------------- #
class ChannelAccountSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ChannelAccount
        fields = [
            "id",
            "user",
            "channel",
            "provider",
            "address_or_id",
            "is_active",
            "last_synced",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "last_synced"]


# ---------------- MESSAGE (LIGHTWEIGHT VERSION) ---------------- #
class MessagePreviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "sender_name",
            "sender",
            "content",
            "metadata",
            "is_read",
            "is_incoming",
            "sent_at",
        ]


# ---------------- FULL MESSAGE ---------------- #
class MessageSerializer(serializers.ModelSerializer):
    account = ChannelAccountSerializer(read_only=True)
    conversation = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "channel",
            "account",
            "external_id",
            "sender",
            "sender_name",
            "recipients",
            "content",
            "metadata",
            "attachments",
            "importance",
            "importance_score",
            "importance_analysis",
            "ai_summary",
            "ai_next_step",
            "ai_people",
            "ai_organizations",
            "ai_related",
            "is_read",
            "is_starred",
            "is_incoming",
            "sent_at",
            "analyzed_at",
            "embedding",
            "embedding_generated",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "importance",
            "importance_score",
            "importance_analysis",
            "ai_summary",
            "ai_next_step",
            "ai_people",
            "ai_organizations",
            "ai_related",
            "embedding",
            "embedding_generated",
            "analyzed_at",
        ]



# ---------------- CONVERSATION ---------------- #
class ConversationSerializer(serializers.ModelSerializer):
    account = ChannelAccountSerializer(read_only=True)
    messages_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "account",
            "thread_id",
            "channel",
            "title",
            "last_message_at",
            "last_sender",
            "summary",
            "next_step_suggestion",
            "actionable_data",
            "people_and_orgs",
            "is_archived",
            "messages_count",
            "created_at",
            "updated_at",
            "last_message",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "messages_count"]

    def get_messages_count(self, obj):
        return obj.messages.count()

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by("-sent_at").first()
        if last_msg:
            return MessagePreviewSerializer(last_msg).data
        return None


# ---------------- NESTED CONVERSATION (WITH PREVIEWS) ---------------- #
class ConversationWithMessagesSerializer(serializers.ModelSerializer):
    account = ChannelAccountSerializer(read_only=True)
    messages = serializers.SerializerMethodField()
    messages_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "account",
            "thread_id",
            "channel",
            "title",
            "last_message_at",
            "last_sender",
            "summary",
            "next_step_suggestion",
            "actionable_data",
            "people_and_orgs",
            "is_archived",
            "messages",
            "messages_count",
            "created_at",
            "updated_at",
        ]

    def get_messages(self, obj):
        # Fetch last 5 messages for preview
        recent_msgs = obj.messages.order_by("-sent_at")[:5]
        return MessagePreviewSerializer(recent_msgs, many=True).data

    def get_messages_count(self, obj):
        return obj.messages.count()


# ---------------- USER RULE ---------------- #
class UserRuleSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = UserRule
        fields = [
            "id",
            "user",
            "name",
            "rule_type",
            "channel",
            "value",
            "importance",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MessageSyncSerializer(serializers.Serializer):
    """Serializer for email sync request"""
    account_id = serializers.IntegerField(required=False)






class MessageSendSerializer(serializers.Serializer):
    message_id = serializers.CharField(required=True)
    to = serializers.EmailField(required=False, allow_blank=True)
    subject = serializers.CharField(required=False, allow_blank=True)
    body = serializers.CharField(required=False, allow_blank=True)
    body_html = serializers.CharField(required=False, allow_blank=True)
    attachments = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True
    )
