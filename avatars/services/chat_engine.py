# avatars/tasks/chat.py
from celery import shared_task
from openai import OpenAI
from avatars.models import AvatarConversation, AvatarMessage
import numpy as np

client = OpenAI()


# ------------------------------
# Helper: Cosine similarity
# ------------------------------
def cosine_similarity(a, b):
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


# ------------------------------
# Helper: Retrieve top-K memorized text
# ------------------------------
def retrieve_relevant_chunks(avatar, query_embedding, top_k=6):
    chunks = list(avatar.chunks.all()[:500])  # safe limit

    if not chunks:
        return ""

    scored = [
        (cosine_similarity(query_embedding, c.embedding), c.text)
        for c in chunks
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    return "\n\n".join(text for _, text in scored[:top_k])


# ==========================================================
# MAIN FUNCTION — Generate the avatar’s response
# ==========================================================
@shared_task
def generate_avatar_reply(conversation_id: str, user_message_id: str):

    # 1. Load objects
    conversation = (
        AvatarConversation.objects
        .select_related("avatar")
        .get(id=conversation_id)
    )
    avatar = conversation.avatar
    user_msg = AvatarMessage.objects.get(id=user_message_id)

    # 2. Embed query
    emb = client.embeddings.create(
        model="text-embedding-3-large",
        input=user_msg.content
    )
    query_embedding = emb.data[0].embedding

    # 3. Retrieve memory context
    memory_context = retrieve_relevant_chunks(avatar, query_embedding)

    # 4. Build system prompt
    system_prompt = f"""
You are **{avatar.name}**, an AI clone of a real person.

PERSONALITY:
{avatar.persona_prompt or "Be warm, clear, helpful, and human-like."}

WRITING STYLE:
{avatar.writing_style or "Use natural, clear, conversational sentences."}

RELEVANT PERSONAL KNOWLEDGE (use only when needed):
{memory_context}

RULES:
- Stay in character
- If unsure, say "I'm not sure"
- Do not invent facts not in memory
    """.strip()

    # 5. Build message history
    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation.messages.order_by("created_at")[-12:]:
        messages.append({
            "role": "user" if msg.role == "visitor" else "assistant",
            "content": msg.content
        })

    # 6. Call OpenAI (non-stream)
    completion = client.responses.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.8,
    )

    final_reply = completion.output_text

    # 7. Save the final avatar reply
    final_message = AvatarMessage.objects.create(
        conversation=conversation,
        role="avatar",
        content=final_reply,
        model_used="gpt-4o-mini",
    )

    return final_message.id
