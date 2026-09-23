from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BotViewSet,
    ConversationViewSet,
    MessageViewSet,
    chat,
)

router = DefaultRouter()

router.register("bots", BotViewSet, basename="bot")
router.register(
    "conversations",
    ConversationViewSet,
    basename="conversation",
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "conversations/<int:conversation_id>/messages/",
        MessageViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="conversation-messages",
    ),
    path("chat/", chat, name="chat-api"),
]
