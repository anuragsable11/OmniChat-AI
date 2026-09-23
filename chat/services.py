import json

import redis
import requests

from .models import Message


OLLAMA_URL = "http://localhost:11434/api/chat"

OLLAMA_MODEL = "qwen3:4b"

# qwen3 is a reasoning model. Thinking tokens cost the same as
# answer tokens but are thrown away, so they are switched off -
# on CPU that is the difference between a reply and a timeout.
OLLAMA_THINK = False

# ~8 tokens/sec on this machine, so this caps a reply at ~25s.
OLLAMA_NUM_PREDICT = 200

# (connect timeout, read timeout between chunks)
OLLAMA_TIMEOUT = (10, 120)

# Turns of history sent to the model. Every extra turn is re-read
# on each request, and prompt evaluation is CPU-bound here, so
# this is the main dial between context and latency.
HISTORY_TURNS = 8

SYSTEM_PROMPT = (
    "You are OmniChat, a helpful assistant. "
    "Answer the user's question directly and concisely. "
    "Do not narrate your reasoning or restate the question."
)


# Redis connection
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
)


def context_key(conversation_id):
    return f"conversation:{conversation_id}:context"


def get_conversation_context(conversation_id):
    """
    Recent turns from Redis as a list of {role, content} dicts,
    or None when the cache is empty or holds an older format.
    """

    raw = redis_client.get(context_key(conversation_id))

    if not raw:
        return None

    try:
        turns = json.loads(raw)

    except (json.JSONDecodeError, TypeError):
        # Older builds cached a flat string - ignore and rebuild.
        return None

    if isinstance(turns, list) and turns:
        return turns

    return None


def build_messages(conversation, message):
    """
    Build the message list for Ollama.

    Real system/user/assistant roles matter: folding everything
    into one user turn makes qwen3 answer in a rambling,
    think-out-loud style instead of replying directly.
    """

    turns = get_conversation_context(conversation.id)

    if turns is None:
        previous = Message.objects.filter(
            conversation=conversation
        ).order_by("-created_at")[:HISTORY_TURNS]

        turns = [
            {
                "role": (
                    "user" if m.sender == "user" else "assistant"
                ),
                "content": m.content,
            }
            for m in reversed(previous)
        ]

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    messages.extend(turns[-HISTORY_TURNS:])

    messages.append({"role": "user", "content": message})

    return messages


def stream_ai_response(conversation, message, on_chunk=None):
    """
    Generate a reply, handing each piece of text to on_chunk as it
    arrives, and return the finished reply.

    Streaming does not make generation faster, but the first words
    show up in a second or two instead of after the whole answer.
    """

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": build_messages(conversation, message),
            "stream": True,
            "think": OLLAMA_THINK,
            "options": {
                "num_predict": OLLAMA_NUM_PREDICT,
            },
        },
        timeout=OLLAMA_TIMEOUT,
        stream=True,
    )

    response.raise_for_status()

    parts = []

    # Ollama streams one JSON object per line.
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue

        try:
            data = json.loads(line)

        except json.JSONDecodeError:
            continue

        if data.get("error"):
            raise RuntimeError(f"Ollama error: {data['error']}")

        chunk = (data.get("message") or {}).get("content") or ""

        if chunk:
            parts.append(chunk)

            if on_chunk is not None:
                on_chunk(chunk)

        if data.get("done"):
            break

    content = "".join(parts).strip()

    if not content:
        raise RuntimeError(
            "Ollama returned an empty response. "
            f"Try raising num_predict (currently {OLLAMA_NUM_PREDICT})."
        )

    return content


def generate_ai_response(conversation, message):
    """
    Blocking version, kept for callers that want the whole reply.
    """

    return stream_ai_response(conversation, message)


def update_conversation_context(
    conversation_id,
    user_message,
    assistant_message,
):
    """
    Cache the latest turns in Redis, trimmed so the prompt cannot
    grow without bound.
    """

    turns = get_conversation_context(conversation_id) or []

    turns.append({"role": "user", "content": user_message})
    turns.append({"role": "assistant", "content": assistant_message})

    redis_client.set(
        context_key(conversation_id),
        json.dumps(turns[-HISTORY_TURNS:]),
    )
