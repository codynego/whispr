# core/ai/embeddings.py
import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

def get_text_embedding(text: str):
    """Generate embedding vector for a given text."""
    try:
        model = "models/embedding-001"
        result = genai.embed_content(model=model, content=text)
        return result["embedding"]
    except Exception as e:
        print("Embedding error:", e)
        return None
