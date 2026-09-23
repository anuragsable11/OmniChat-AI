import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Conversation


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Pushes finished AI replies to the browser.

    Celery generates the answer in the background, so the HTTP
    request cannot carry it - it arrives here instead.
    """

    @database_sync_to_async
    def user_owns_conversation(self, user, conversation_id):
        return Conversation.objects.filter(
            id=conversation_id,
            user=user,
        ).exists()

    async def connect(self):

        self.conversation_id = self.scope[
            "url_route"
        ]["kwargs"]["conversation_id"]

        user = self.scope.get("user")

        # Reject anonymous sockets outright.
        if user is None or not user.is_authenticated:
            await self.close(code=4001)
            return

        # ...and anyone reaching for a conversation they do not own.
        owns = await self.user_owns_conversation(
            user,
            self.conversation_id,
        )

        if not owns:
            await self.close(code=4003)
            return

        self.room_group_name = f"chat_{self.conversation_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send(
            text_data=json.dumps({
                "type": "connection",
                "message": "WebSocket connected successfully.",
            })
        )

    async def disconnect(self, close_code):

        # connect() can bail out before the group is joined.
        if not hasattr(self, "room_group_name"):
            return

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        """
        The browser posts messages over HTTP, so nothing is
        expected here. Kept as a ping for debugging.
        """

        try:
            data = json.loads(text_data)

        except json.JSONDecodeError:
            return

        if data.get("type") == "ping":
            await self.send(
                text_data=json.dumps({"type": "pong"})
            )

    async def chat_start(self, event):
        """
        Generation has begun - the UI replaces its spinner with an
        empty bubble that the chunks below fill in.
        """

        await self.send(
            text_data=json.dumps({"type": "stream_start"})
        )

    async def chat_chunk(self, event):
        """
        One piece of the reply, sent as the model produces it.
        """

        await self.send(
            text_data=json.dumps({
                "type": "stream_chunk",
                "text": event["text"],
            })
        )

    async def chat_message(self, event):
        """
        Fired by generate_ai_response_task once the reply is saved.
        Carries the full text, so a client that joined late or
        dropped chunks still lands on the correct answer.
        """

        await self.send(
            text_data=json.dumps({
                "type": "ai_response",
                "message": event["message"],
                "message_id": event["message_id"],
            })
        )

    async def chat_error(self, event):
        """
        Fired when generation fails, so the UI can stop waiting
        instead of showing a spinner forever.
        """

        await self.send(
            text_data=json.dumps({
                "type": "error",
                "message": event["message"],
            })
        )
