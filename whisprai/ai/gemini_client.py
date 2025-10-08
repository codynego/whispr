# core/ai/gemini_client.py
from .retriever import retrieve_relevant_emails
import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

def get_gemini_response(prompt, user, model="gemini-1.5-flash", temperature=0.7, max_output_tokens=500):
    emails = retrieve_relevant_emails(user, prompt)
    context = "\n\n".join([
        f"From: {e.sender}\nSubject: {e.subject}\nBody: {e.body[:300]}..."
        for e in emails
    ]) or "No relevant emails found."

    full_prompt = f"""
    You are an intelligent email assistant for {user.email}.
    Use the context from recent emails to respond accurately.

    === EMAIL CONTEXT START ===
    {context}
    === EMAIL CONTEXT END ===

    User Query: {prompt}
    """

    model_instance = genai.GenerativeModel(model)
    response = model_instance.generate_content(full_prompt)
    return response.text
