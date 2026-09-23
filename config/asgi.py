import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

# Must be built before importing anything that touches models,
# which is why the routing import sits below this line.
django_asgi_app = get_asgi_application()

from chat.routing import websocket_urlpatterns  # noqa: E402


application = ProtocolTypeRouter({
    "http": django_asgi_app,

    # AuthMiddlewareStack reads the session cookie and puts the
    # signed-in user on scope["user"], which the consumer needs
    # to check who owns the conversation.
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
