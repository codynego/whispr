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
    chunks = file.embedding

    if not chunks:
        return "No content available to answer from this file."

    # Handle single embedding case
    if isinstance(chunks, list) and all(isinstance(x, float) for x in chunks):
        chunks = [{"chunk": getattr(file, "content", ""), "embedding": chunks}]

    if not isinstance(chunks, list):
        return "Invalid file embeddings format."

    # Generate embedding for user query
    query_embedding = generate_embedding(user_query)
    print("Query embedding generated.")  # Debug print

    # Rank chunks by similarity
    ranked_chunks = []
    for chunk in chunks:
        emb = chunk.get("embedding")
        text = chunk.get("chunk", "")
        if not emb or not isinstance(emb, list):
            continue
        score = cosine_similarity(query_embedding, emb)
        ranked_chunks.append({"chunk": text, "score": score})
    print(f"Ranked {len(ranked_chunks)} chunks based on similarity.")  # Debug print

    if not ranked_chunks:
        return "No valid content available to answer from this file."

    # Select top-k relevant chunks
    top_chunks = sorted(ranked_chunks, key=lambda x: x["score"], reverse=True)[:top_k]
    context_text = "\n\n".join([c["chunk"] for c in top_chunks])
    print("Top chunks selected for context:\n", context_text)  # Debug print

    prompt = f"""
You are an AI assistant. Use the following file content to answer the user's question:

{context_text}

Question: {user_query}

If the file does not contain enough information to answer the question accurately, respond:
'I could not find sufficient information in the file to answer this.'
Answer concisely and clearly.
"""

    # Call OpenAI LLM
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        answer = response.choices[0].message.content.strip()
        print(f"Context used for answering:\n{context_text}\n")  # Debug print
        print(f"Answer generated:\n{answer}\n")  # Debug print
        return answer
    except Exception as e:
        return f"Error generating answer: {e}"
