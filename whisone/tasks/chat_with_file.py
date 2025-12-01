from openai import OpenAI
import numpy as np
from django.conf import settings
from whisone.models import UploadedFile
from whisone.utils.embedding_utils import generate_embedding


def cosine_similarity(vec1, vec2):
    vec1, vec2 = np.array(vec1), np.array(vec2)
    norm1, norm2 = np.linalg.norm(vec1), np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def chat_with_file(file: UploadedFile, user_query: str, top_k: int = 5) -> str:
    """
    Robust chat with file that handles multiple embedding storage formats.
    """
    raw_chunks = file.embedding  # This could be None, list of dicts, or even a single list

    if not raw_chunks:
        return "No content available to answer from this file."

    # Normalize everything into a list of dicts: [{"chunk": str, "embedding": list[float]}]
    chunks = []

    # Case 1: Single embedding stored as a plain list (old format)
    if isinstance(raw_chunks, list) and raw_chunks and isinstance(raw_chunks[0], float):
        text = getattr(file, "content", "") or "No text content available."
        chunks = [{"chunk": text, "embedding": raw_chunks}]

    # Case 2: List of embeddings (each embedding is a list)
    elif isinstance(raw_chunks, list) and raw_chunks and isinstance(raw_chunks[0], list):
        text = getattr(file, "content", "") or ""
        # Assume whole file if no per-chunk text stored
        chunks = [{"chunk": text, "embedding": emb} for emb in raw_chunks if isinstance(emb, list)]

    # Case 3: Proper list of dicts (new/current format)
    elif isinstance(raw_chunks, list):
        for item in raw_chunks:
            if isinstance(item, dict):
                embedding = item.get("embedding") or item.get("vector")
                text = item.get("chunk") or item.get("text") or ""
                if isinstance(embedding, list):
                    chunks.append({"chunk": text, "embedding": embedding})
            elif isinstance(item, list):  # fallback: raw embedding list
                chunks.append({"chunk": getattr(file, "content", ""), "embedding": item})

    # Final safety check
    if not chunks:
        return "No valid embedded content found in this file."

    # Generate query embedding
    try:
        query_embedding = generate_embedding(user_query)
    except Exception as e:
        return f"Failed to generate embedding for query: {e}"

    # Score all chunks
    scored_chunks = []
    for chunk in chunks:
        emb = chunk["embedding"]
        if not isinstance(emb, list) or len(emb) == 0:
            continue
        score = cosine_similarity(query_embedding, emb)
        scored_chunks.append({"chunk": chunk["chunk"], "score": score})

    if not scored_chunks:
        return "Could not compute similarity with any content."

    # Get top-k
    top_chunks = sorted(scored_chunks, key=lambda x: x["score"], reverse=True)[:top_k]
    context_text = "\n\n".join([c["chunk"].strip() for c in top_chunks if c["chunk"].strip()])

    if not context_text.strip():
        return "No relevant text content found to answer your question."

    # Build prompt
    prompt = f"""
You are a helpful assistant answering questions based only on the provided content from an uploaded file.

Use this content to answer the question:

{context_text}

Question: {user_query}

Instructions:
- Answer concisely and accurately.
- If the content does not contain enough information, say: "I could not find sufficient information in the file to answer this."
- Do not make up information.

Answer:
""".strip()

    # Call OpenAI
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        return f"Error generating answer from AI: {str(e)}"