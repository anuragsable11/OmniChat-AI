from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Bot, Conversation, Message
from .serializers import (
    BotSerializer,
    ConversationSerializer,
    MessageSerializer,
)
from .tasks import generate_ai_response_task


class BotViewSet(viewsets.ModelViewSet):
    queryset = Bot.objects.all()
    serializer_class = BotSerializer
    permission_classes = [IsAuthenticated]


class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(
            user=self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(
            conversation__user=self.request.user
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat(request):

    # Get request data
    message_text = request.data.get("message")
    conversation_id = request.data.get("conversation_id")

    # Validate message
    if not message_text:
        return Response(
            {"error": "Message is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate conversation ID
    if not conversation_id:
        return Response(
            {"error": "conversation_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Make sure conversation belongs to logged-in user
    try:
        conversation = Conversation.objects.get(
            id=conversation_id,
            user=request.user,
        )

    except Conversation.DoesNotExist:
        return Response(
            {"error": "Conversation not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Save user's message
    user_message = Message.objects.create(
        conversation=conversation,
        sender="user",
        content=message_text,
    )

    # Send AI generation to Celery
    task = generate_ai_response_task.delay(
        conversation.id,
        user_message.id,
    )

    # Return immediately
    return Response({
        "conversation_id": conversation.id,

        "user_message": {
            "id": user_message.id,
            "content": user_message.content,
        },

        "task_id": task.id,

        "status": "AI response is being generated",
    })