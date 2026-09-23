from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Bot, Conversation, Message


class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = "__all__"


class ConversationSerializer(serializers.ModelSerializer):

    # Sidebar label, resolved by the model.
    display_title = serializers.CharField(read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "bot",
            "title",
            "display_title",
            "created_at",
            "updated_at",
        ]

        # The view sets the owner from request.user, so it must
        # not be accepted (or required) from the client.
        read_only_fields = ["created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # "New Chat" posts an empty body, so the bot is chosen
        # server-side when the client does not name one.
        self.fields["bot"].required = False


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "content",
            "created_at",
        ]

        # The conversation comes from the URL, not the body.
        read_only_fields = ["conversation", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]
