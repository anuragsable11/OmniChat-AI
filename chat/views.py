from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .services import generate_ai_response

from .models import Bot, Conversation, Message
from .serializers import (
    BotSerializer,
    ConversationSerializer,
    MessageSerializer,
)


class BotViewSet(viewsets.ModelViewSet):
    queryset = Bot.objects.all()
    serializer_class = BotSerializer
    permission_classes = [IsAuthenticated]


class ConversationViewSet(viewsets.ModelViewSet):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filer(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(
            conversation__user=self.request.user
        )

    def perform_create(self, serializer):
        conversation_id = self.kwargs["conversation_id"]

        conversation = Conversation.objects.get(
            id=conversation_id,
            user=self.request.user
        )

        serializer.save(
            conversation=conversation,
            sender="user"
        )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat(request):
    message_text = request.data.get("message")
    conversation_id = request.data.get("conversation_id")

    if not message_text:
        return Response(
            {"error": "Message is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not conversation_id:
        return Response(
            {"error": "conversation_id is required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        conversation = Conversation.objects.get(
            id=conversation_id,
            user=request.user
        )
    except Conversation.DoesNotExist:
        return Response(
            {"error": "Conversation not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    user_message = Message.objects.create(
        conversation=conversation,
        sender="user",
        content=message_text
    )

    ai_response = generate_ai_response(message_text)

    assistant_message = Message.objects.create(
        conversation=conversation,
        sender="assistant",
        content=ai_response
    )

    return Response({
        "conversation_id": conversation.id,
        "user_message": {
            "id": user_message.id,
            "content": user_message.content
        },
        "assistant_message": {
            "id": assistant_message.id,
            "content": assistant_message.content
        }
    })        