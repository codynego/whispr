# avatars/tasks/chat.py
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from openai import OpenAI
from avatars.models import AvatarConversation, AvatarMessage, AvatarMemoryChunk
import numpy as np

client = OpenAI()
channel_layer = get_channel_layer()

def cosine_similarity(a, b):
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def retrieve_relevant_chunks(avatar, query_embedding, top_k=6):
    chunks = list(avatar.chunks.all()[:500])  # limit for speed
    if not chunks:
        return ""

    similarities = [
        (cosine_similarity(query_embedding, chunk.embedding), chunk.text)
        for chunk in chunks
    ]
    similarities.sort(reverse=True, key=lambda x: x[0])
    return "\n\n".join(text for _, text in similarities[:top_k])

@shared_task
def generate_streaming_response(conversation_id: str, user_message_id: str):
    conversation = AvatarConversation.objects.select_related("avatar").get(id=conversation_id)
    avatar = conversation.avatar
    user_msg = AvatarMessage.objects.get(id=user_message_id)

    # 1. Embed the user message
    query_embedding = client.embeddings.create(
        model="text-embedding-3-large",
        input=user_msg.content
    ).data[0].embedding

    # 2. Retrieve relevant knowledge
    relevant_knowledge = retrieve_relevant_chunks(avatar, query_embedding, top_k=6)

    # 3. Build system prompt with retrieved context
    system_prompt = f"""
You are {avatar.name}, an AI version of a real person.

PERSONALITY & TONE:
{avatar.persona_prompt or "You are friendly and direct."}

WRITING STYLE:
{avatar.writing_style or "Write naturally with clear sentences."}

RELEVANT KNOWLEDGE (use this to answer accurately):
{relevant_knowledge}

INSTRUCTIONS:
- Always stay in character
- If you don't know something, say "I'm not sure" — never make things up
- Use the knowledge above when relevant
""".strip()

    # 4. Build message history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation.messages.order_by("created_at")[-12:]:
        role = "user" if msg.role == "visitor" else "assistant"
        messages.append({"role": role, "content": msg.content})

    # 5. Stream response
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.8,
        stream=True,
    )

    full_reply = ""
    temp_message_id = str(user_message_id)  # reuse until final

    for chunk in stream:
        if content := chunk.choices[0].delta_and_delta.get("content"):
            full_reply += content

            async_to_sync(channel_layer.group_send)(
                f"chat_{conversation.id}",
                {
                    "type": "chat.message",
                    "message": {
                        "id": temp_message_id,
                        "role": "avatar",
                        "content": content,
                        "is_streaming": True
                    }
                }
            )

    # Save final complete message
    final_message = AvatarMessage.objects.create(
        conversation=conversation,
        role="avatar",
        content=full_reply.strip(),
        model_used="gpt-4o-mini",
    )

    async_to_sync(channel_layer.group_send)(
        f"chat_{conversation.id}",
        {
            "type": "chat.message",
            "message": {
                "id": str(final_message.id),
                "role": "avatar",
                "content": full_reply.strip(),
                "is_streaming": False,
                "complete": True
            }
        }
    )