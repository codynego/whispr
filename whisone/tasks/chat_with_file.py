import openai
import numpy as np
from django.conf import settings
from whisone.models import UploadedFile
from whisone.utils.embedding_utils import generate_embedding

# Helper: cosine similarity
def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def chat_with_file(file: UploadedFile, user_query: str, top_k: int = 5) -> str:
    """
    Given a file and a user query, find the most relevant chunks and answer.
    """
    # 1. Split file content into chunks if not already done
    # (Assume you store embeddings per chunk as list of dicts: [{"chunk": "...", "embedding": [...]}, ...])
    chunks = file.embedding  # list of dicts with 'chunk' and 'embedding'

    if not chunks:
        return "No content available to answer from this file."

    # 2. Get query embedding

    query_embedding = generate_embedding(user_query)

    # 3. Rank chunks by cosine similarity
    for chunk in chunks:
        chunk["score"] = cosine_similarity(np.array(query_embedding), np.array(chunk["embedding"]))

    chunks_sorted = sorted(chunks, key=lambda x: x["score"], reverse=True)
    top_chunks = chunks_sorted[:top_k]

    # 4. Construct prompt for LLM
    context_text = "\n\n".join([c["chunk"] for c in top_chunks])
    prompt = f"""
    You are an AI assistant. Answer the user question using ONLY the following file content:

    {context_text}

    Question: {user_query}
    Answer concisely, clearly, and accurately.
    """

    # 5. Call OpenAI LLM
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    answer = response.choices[0].message.content.strip()
    return answer
