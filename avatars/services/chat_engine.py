# avatars/tasks/chat.py
from celery import shared_task
from openai import OpenAI
from avatars.models import AvatarConversation, AvatarMessage
import numpy as np
from django.conf import settings
from whatsapp.tasks import send_whatsapp_text

client = OpenAI(api_key=settings.OPENAI_API_KEY)


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

    scored = []

    for c in chunks:
        emb_list = c.embedding  # <-- could be list OR list of lists

        if not emb_list:
            continue

        # If it's a single embedding, wrap it
        if isinstance(emb_list[0], float):
            emb_list = [emb_list]

        # compute similarity against each embedding
        max_score = max(
            cosine_similarity(query_embedding, emb)
            for emb in emb_list
        )

        scored.append((max_score, c.text))

    scored.sort(key=lambda x: x[0], reverse=True)

    return "\n\n".join(text for _, text in scored[:top_k])



# ==========================================================
# MAIN FUNCTION — Generate the avatar’s response
# ==========================================================
@shared_task
def generate_avatar_reply(conversation_id: str, user_message_id: str, whatsapp_mode: bool = False) -> str:
    user = AvatarConversation.objects.get(id=conversation_id).user
    sender_number = user.whatsapp if user else None
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
        model="text-embedding-3-small",
        input=user_msg.content
    )
    query_embedding = emb.data[0].embedding

    # 3. Retrieve memory context
    memory_context = retrieve_relevant_chunks(avatar, query_embedding)

    # 4. Build system prompt
    system_prompt = f"""
You are **{avatar.name}**, an AI version of a real person.

Your job is to respond exactly the way this person would — matching their tone, behavior, writing style, opinions, and communication patterns.

========================
PERSONALITY BLUEPRINT
========================
{avatar.persona_prompt or "The person is friendly, direct, and thoughtful."}

========================
WRITING STYLE RULES
========================
- {avatar.tone or "Use short, clear, natural sentences."}
- Match pacing, humor, energy level, phrasing, and emotional tone of the person.
- Mirror their typical word choice (slang, emojis, fillers, punctuation style).
- If they are formal, stay formal. If they are casual, stay casual.

========================
PERSONAL KNOWLEDGE
(Use ONLY if relevant and true)
========================
{memory_context}

========================
CONVERSATION LOGIC
========================
- Stay fully in character as the person — never as “an AI”.
- Speak with the same confidence the person normally uses.
- If you don’t have information, say: “I’m not sure about that.”
- Do NOT invent facts not present in the memory or user messages.
- If the user asks about something you don’t know, be honest.
- Keep responses concise and human-like unless the person usually writes long.

========================
INTERACTION BEHAVIOR
========================
- Adapt tone depending on who you talk to (friendly, professional, empathetic, playful — according to the real person’s behavior).
- Use emotions or expressiveness only if authentic to the person’s style.
- If the person normally uses emojis, you can use them. If not, avoid them.
- Maintain continuity of personality across the full conversation.

========================
MISSION
========================
Your purpose is to realistically represent **{avatar.name}** — not to be a generic assistant.
""".strip()


    # 5. Build message history
    messages = [{"role": "system", "content": system_prompt}]
    recent_messages = conversation.messages.order_by("-created_at")[:12][::-1]

    for msg in recent_messages:
        messages.append({
            "role": "user" if msg.role == "visitor" else "assistant",
            "content": msg.content
        })
    # 6. Call OpenAI (non-stream)
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.8,
    )
    print("memory_context:", memory_context)

    final_reply = completion.choices[0].message.content
    print(f"OpenAI response: {final_reply}")

    # 7. Save the final avatar reply
    final_message = AvatarMessage.objects.create(
        conversation=conversation,
        role="avatar",
        content=final_reply,
    )

    if whatsapp_mode:
        send_whatsapp_text.delay(
            user_id=user.id,
            text=final_reply
        )


    return final_message.id
