import requests
import redis

from .models import Message


# Redis connection
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
)


def get_conversation_context(conversation_id):
    """
    Get conversation context from Redis.
    """

    key = f"conversation:{conversation_id}:context"

    context = redis_client.get(key)

    if context:
        return context

    return None


def generate_ai_response(conversation, message):
    """
    Generate an AI response using Ollama + Qwen3.
    Redis provides fast conversation context.
    """

    context = get_conversation_context(conversation.id)

    if not context:
        previous_messages = Message.objects.filter(
            conversation=conversation
        ).order_by("created_at")

        context = ""

        for msg in previous_messages:
            role = "User" if msg.sender == "user" else "Assistant"
            context += f"{role}: {msg.content}\n"

    prompt = f"""
You are a concise chatbot.

Answer the user's question directly.
Do not explain your reasoning.
Do not think out loud.
Keep the answer short unless the user asks for detail.

Conversation:
{context}

User: {message}

Answer:
"""

    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "qwen3:4b",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "stream": False,
            "think": True,
            "options": {
                "num_predict": 500,
            },
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    message_data = data.get("message", {})

    content = (message_data.get("content") or "").strip()

    if not content:
        raise RuntimeError(
            "Ollama returned an empty response."
        )

    return content

def update_conversation_context(
    conversation_id,
    user_message,
    assistant_message,
):
    """
    Store conversation context in Redis.
    """

    key = f"conversation:{conversation_id}:context"

    existing_context = redis_client.get(key)

    if existing_context:
        context = (
            existing_context
            + f"\nUser: {user_message}"
            + f"\nAssistant: {assistant_message}"
        )

    else:
        context = (
            f"User: {user_message}"
            f"\nAssistant: {assistant_message}"
        )

    redis_client.set(key, context)