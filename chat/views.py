from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
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


# ---------------------------------------------------------------
# Pages
# ---------------------------------------------------------------

def landing_page(request):
    """
    Public marketing page. Links signed-in users straight to the app.
    """

    return render(request, "landing.html")


def login_page(request):
    """
    Username / password form. Already-signed-in users skip it.
    """

    if request.user.is_authenticated:
        return redirect("chat_page")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            return render(
                request,
                "login.html",
                {
                    "error": "Invalid username or password.",
                    "username": username,
                },
                status=401,
            )

        login(request, user)

        return redirect("chat_page")

    return render(request, "login.html")


def logout_page(request):
    logout(request)

    return redirect("login_page")


@login_required
def chat_page(request):
    """
    The single-page chat UI. Conversations load over the API.
    """

    return render(request, "chat.html")


# ---------------------------------------------------------------
# API
# ---------------------------------------------------------------

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
        ).order_by("-updated_at")

    def perform_create(self, serializer):
        bot = serializer.validated_data.get("bot")

        # "New Chat" sends no bot, so fall back to any active one
        # and create a default if the database has none yet.
        if bot is None:
            bot = Bot.objects.filter(is_active=True).first()

            if bot is None:
                bot = Bot.objects.create(
                    name="OmniChat AI",
                    description="Default assistant.",
                )

        serializer.save(user=self.request.user, bot=bot)


class MessageViewSet(viewsets.ModelViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_conversation(self):
        """
        Resolve the conversation from the URL, 404-ing when it
        belongs to somebody else.
        """

        return get_object_or_404(
            Conversation,
            id=self.kwargs["conversation_id"],
            user=self.request.user,
        )

    def get_queryset(self):
        # Scoped to the conversation in the URL - without this the
        # endpoint returns every message the user has ever sent.
        return Message.objects.filter(
            conversation=self.get_conversation()
        ).order_by("created_at")

    def perform_create(self, serializer):
        serializer.save(
            conversation=self.get_conversation(),
            sender="user",
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat(request):

    # Get request data
    message_text = (request.data.get("message") or "").strip()
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

    # Name the chat after its opening message
    if not conversation.title:
        conversation.title = message_text[:40]

    conversation.save(update_fields=["title", "updated_at"])

    # Hand generation to Celery so the request returns at once
    task = generate_ai_response_task.delay(
        conversation.id,
        user_message.id,
    )

    return Response({
        "conversation_id": conversation.id,

        "user_message": {
            "id": user_message.id,
            "content": user_message.content,
        },

        "task_id": task.id,

        "status": "AI response is being generated",
    })
