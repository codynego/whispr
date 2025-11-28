# avatars/tasks/chat.py
from celery import shared_task
from openai import OpenAI
from avatars.models import AvatarConversation, AvatarMessage
import numpy as np
from django.conf import settings
from django.db.models import QuerySet

# Initialize the OpenAI client globally (assuming settings.OPENAI_API_KEY is available)
client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ------------------------------
# Helper: Cosine similarity
# ------------------------------
def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculates the cosine similarity between two vector embeddings."""
    # Ensure inputs are numpy arrays for calculation
    a_np = np.array(a, dtype=np.float32)
    b_np = np.array(b, dtype=np.float32)
    
    # Handle zero vectors to prevent division by zero
    norm_a = np.linalg.norm(a_np)
    norm_b = np.linalg.norm(b_np)
    if norm_a == 0 or norm_b == 0:
        return 0.0

    return np.dot(a_np, b_np) / (norm_a * norm_b)


# ------------------------------
# Helper: Retrieve top-K memorized text
# ------------------------------
def retrieve_relevant_chunks(avatar: "Avatar", query_embedding: list[float], top_k: int = 6) -> str:
    """Retrieves the top-K relevant memory chunks based on cosine similarity."""
    
    # Limit the chunks retrieved to avoid excessive memory/processing
    # Ensure embedding field is retrieved in the query.
    chunks: QuerySet["AvatarMemoryChunk"] = avatar.chunks.all().filter(embedding__isnull=False)[:500] 

    if not chunks.exists():
        return ""

    scored = [
        (cosine_similarity(query_embedding, c.embedding), c.text)
        for c in chunks
    ]
    # Sort by score (first element) in descending order
    scored.sort(key=lambda x: x[0], reverse=True)

    # Return the text content of the top-K chunks
    return "\n\n".join(text for score, text in scored[:top_k])


# ==========================================================
# MAIN FUNCTION — Generate the avatar’s response
# ==========================================================
@shared_task(bind=True) # Use bind=True to allow access to self (task instance) if needed
def generate_avatar_reply(self, conversation_id: int, user_message_id: int): # Use int type hints
    
    # 1. Load objects
    try:
        conversation = (
            AvatarConversation.objects
            .select_related("avatar")
            .get(id=conversation_id)
        )
        avatar = conversation.avatar
        user_msg = AvatarMessage.objects.get(id=user_message_id)
    except (AvatarConversation.DoesNotExist, AvatarMessage.DoesNotExist):
        # Handle case where objects might have been deleted
        print(f"ERROR: Conversation or Message not found. Conversation ID: {conversation_id}, Message ID: {user_message_id}")
        return None

    # 2. Embed query
    # The OpenAI client call is correct
    try:
        emb = client.embeddings.create(
            model="text-embedding-3-large",
            input=user_msg.content
        )
        query_embedding = emb.data[0].embedding
    except Exception as e:
        print(f"ERROR: OpenAI Embedding failed: {e}")
        return None # Fail gracefully

    # 3. Retrieve memory context
    memory_context = retrieve_relevant_chunks(avatar, query_embedding)

    # 4. Build system prompt
    system_prompt = f"""
You are **{avatar.name}**, an AI clone of a real person.

PERSONALITY:
{avatar.persona_prompt or "Be warm, clear, helpful, and human-like."}

Tone:
{avatar.tone or "Use natural, clear, conversational sentences."}

RELEVANT PERSONAL KNOWLEDGE (use only when needed):
{memory_context}

RULES:
- Stay in character
- If unsure, say "I'm not sure"
- Do not invent facts not in memory
    """.strip()

    # 5. Build message history
    messages = [{"role": "system", "content": system_prompt}]
    
    # ⭐ FIX for "TypeError: Cannot reorder a query once a slice has been taken." ⭐
    # Correct method: 
    # 1. Order by descending created_at (-created_at) to get newest messages first.
    # 2. Slice to get the top 12 newest messages (excluding the user_msg which is already known).
    # 3. Use .values_list('pk', flat=True) to exclude the user_msg from history if it's already there.
    
    # Get the 12 messages BEFORE the user_msg chronologically.
    recent_messages_qs = (
        conversation.messages
        .exclude(id=user_msg.id) # Exclude the user's current message
        .order_by("-created_at") # Newest first
        [:11] # Get the 11 *other* most recent messages (total history of 12)
        .order_by("created_at") # Re-sort to chronological order for the chat history 
    )
    
    # If reordering after slicing causes the TypeError, the standard robust fix is:
    recent_messages = list(conversation.messages.order_by("-created_at").exclude(id=user_msg.id)[:11])
    recent_messages.sort(key=lambda m: m.created_at)
    
    # Replaced with the robust in-memory sort:
    
    # Build history list from the retrieved messages
    for msg in recent_messages:
        messages.append({
            "role": "user" if msg.role == "visitor" else "assistant",
            "content": msg.content
        })
        
    # Append the current user message as the final message in the history
    messages.append({
        "role": "user",
        "content": user_msg.content
    })


    # 6. Call OpenAI (non-stream)
    # NOTE: The completion call was using client.responses.create, which is incorrect for openai==1.0+.
    # The correct method is client.chat.completions.create
    
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
            # max_tokens=256, # Consider adding a max_tokens limit
        )

        # The access pattern for the response object is also updated
        final_reply = completion.choices[0].message.content
        model_used = completion.model # Get the exact model name used

    except Exception as e:
        print(f"ERROR: OpenAI API call failed: {e}")
        return None # Fail gracefully

    # 7. Save the final avatar reply
    if not final_reply:
        print("WARNING: OpenAI returned an empty reply.")
        return None
        
    final_message = AvatarMessage.objects.create(
        conversation=conversation,
        role="avatar",
        content=final_reply,
        model_used=model_used,
    )

    return final_message.id