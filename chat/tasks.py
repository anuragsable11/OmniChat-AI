import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer

from .models import Conversation, Message
from .services import (
    stream_ai_response,
    update_conversation_context,
)


logger = logging.getLogger(__name__)


def push_to_group(conversation_id, payload):
    """
    Send an event to everyone watching this conversation.
    """

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f"chat_{conversation_id}",
        payload,
    )


@shared_task
def test_celery_task():
    print("Celery task executed successfully!")

    return "Celery is working!"


@shared_task
def generate_ai_response_task(conversation_id, message_id):

    conversation = Conversation.objects.get(id=conversation_id)

    user_message = Message.objects.get(id=message_id)

    # Tell the browser to swap the spinner for an empty bubble.
    push_to_group(
        conversation_id,
        {"type": "chat_start"},
    )

    def on_chunk(text):
        push_to_group(
            conversation_id,
            {
                "type": "chat_chunk",
                "text": text,
            },
        )

    try:
        ai_response = stream_ai_response(
            conversation,
            user_message.content,
            on_chunk=on_chunk,
        )

    except Exception as exc:
        # Without this the browser waits forever: the socket only
        # ever hears about successful generations.
        logger.exception("AI generation failed")

        push_to_group(
            conversation_id,
            {
                "type": "chat_error",
                "message": f"Could not generate a reply: {exc}",
            },
        )

        raise

    # Save AI response
    assistant_message = Message.objects.create(
        conversation=conversation,
        sender="assistant",
        content=ai_response,
    )

    # Keep the Redis context warm for the next turn
    try:
        update_conversation_context(
            conversation.id,
            user_message.content,
            ai_response,
        )

    except Exception:
        # Redis here is only a cache - SQLite still has the
        # history, so a cache failure must not lose the reply.
        logger.warning(
            "Could not update Redis context", exc_info=True
        )

    # Final event: carries the saved id and the complete text, so a
    # client that missed chunks still ends up correct.
    push_to_group(
        conversation_id,
        {
            "type": "chat_message",
            "message": ai_response,
            "message_id": assistant_message.id,
        },
    )

    return ai_response
