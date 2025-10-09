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

import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

def generate_email_embedding(email):
    """
    Generate an embedding vector for a given email using Gemini.
    """
    try:
        text = f"Subject: {email.subject}\nBody: {email.body}"
        model = genai.GenerativeModel("models/embedding-001")
        result = model.embed_content(text=text)
        return result["embedding"]
    except Exception as e:
        print(f"⚠️ Embedding generation failed for {email.id}: {e}")
        return None

