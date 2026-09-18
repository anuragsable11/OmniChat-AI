from celery import shared_task

from .models import Conversation, Message
from .services import generate_ai_response


@shared_task
def test_celery_task():
    print("Celery task executed successfully!")
    return "Celery is working!"


@shared_task
def generate_ai_response_task(conversation_id, message_id):
    conversation = Conversation.objects.get(
        id=conversation_id
    )

    user_message = Message.objects.get(
        id=message_id
    )

    ai_response = generate_ai_response(
        conversation,
        user_message.content,
    )

    Message.objects.create(
        conversation=conversation,
        sender="assistant",
        content=ai_response,
    )

    return ai_response