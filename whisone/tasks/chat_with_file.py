import openai
import numpy as np
from django.conf import settings
from whisone.models import UploadedFile
from whisone.utils.embedding_utils import generate_embedding

# -----------------------
# Helper: cosine similarity
# -----------------------
def cosine_similarity(vec1, vec2):
    vec1, vec2 = np.array(vec1), np.array(vec2)
    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

# -----------------------
# Main chat function
# -----------------------
def chat_with_file(file: UploadedFile, user_query: str, top_k: int = 5) -> str:
    """
    Given a file and a user query, find the most relevant chunks (or the whole file)
    and generate an answer using OpenAI.
    """
    # 1. Get embeddings from file
    chunks = file.embedding

    if not chunks:
        return "No content available to answer from this file."

    # Handle single embedding case (old format)
    if isinstance(chunks, list) and all(isinstance(x, float) for x in chunks):
        chunks = [{"chunk": getattr(file, "content", ""), "embedding": chunks}]

    # Validate chunked embeddings
    if not isinstance(chunks, list):
        return "Invalid file embeddings format."

    # 2. Generate embedding for user query
    query_embedding = generate_embedding(user_query)

    # 3. Rank chunks by cosine similarity
    ranked_chunks = []
    for chunk in chunks:
        emb = chunk.get("embedding")
        text = chunk.get("chunk", "")
        if not emb or not isinstance(emb, list):
            continue
        score = cosine_similarity(query_embedding, emb)
        ranked_chunks.append({"chunk": text, "score": score})

    if not ranked_chunks:
        return "No valid content available to answer from this file."

    # 4. Pick top-k chunks
    top_chunks = sorted(ranked_chunks, key=lambda x: x["score"], reverse=True)[:top_k]

    # 5. Construct prompt for LLM
    context_text = "\n\n".join([c["chunk"] for c in top_chunks])
    print(f"Context used for answering:\n{context_text}\n")  # Debug print
    prompt = f"""
You are an AI assistant. Answer the user question using ONLY the following file content:

{context_text}

Question: {user_query}
Answer concisely, clearly, and accurately.
"""

    # 6. Call OpenAI
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        return f"Error generating answer: {e}"
