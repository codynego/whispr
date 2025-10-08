# core/ai/gemini_client.py
import google.generativeai as genai
from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

def get_gemini_response(prompt, model="gemini-flash-latest", temperature=0.7, max_output_tokens=500):
    model = genai.GenerativeModel(model)
    response = model.generate_content(prompt)
    return response.text
