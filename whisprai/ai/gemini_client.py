from .retriever import retrieve_relevant_emails
import google.generativeai as genai
from django.conf import settings
from django.utils import timezone
import json
from assistant.tasks import execute_ai_action  # handle actual AI-triggered actions

genai.configure(api_key=settings.GEMINI_API_KEY)
from celery import shared_task
from django.contrib.auth import get_user_model

# In-memory conversation state
conversation_memory = {}
User = get_user_model()


def get_gemini_response(prompt, user_id, task_type="conversational", model="gemini-2.5-flash", temperature=0.7, max_output_tokens=800):
    """
    Unified entry point for AI assistant.
    Handles:
        - conversational: chat, question answering, or task reasoning
        - summarize: summarize emails or text content
        - report: generate email-style reports
        - classify: categorize email intent or topic

    Dynamically retrieves context (emails) only when needed.
    """
    user = User.objects.get(id=user_id)

    # === STEP 1: Load conversation context ===
    prev_context = conversation_memory.get(user.id, "")

    # === STEP 2: Retrieve email context only for conversational tasks ===
    email_context = ""
    if task_type == "conversational":
        emails = retrieve_relevant_emails(user, prompt)
        email_context = "\n\n".join([
            f"From: {e.sender}\nSubject: {e.subject}\nBody: {e.body}..."
            for e in emails
        ]) or "No relevant emails found."

    # === STEP 3: Build task-specific prompt templates ===
    if task_type == "conversational":
        system_prompt = f"""
        You are LensraMail — an intelligent, context-aware assistant helping {user.email}.
        You can analyze emails, answer questions, summarize threads, and take actions such as drafting emails or setting reminders.

        Always reply in JSON format:
        {{
            "intent": "<send_email|set_reminder|reply|none>",
            "required_fields": {{}},
            "fields": {{}},
            "reply": "<your response to the user>"
        }}

        Context from previous conversation:
        {prev_context}

        === EMAIL CONTEXT START ===
        {email_context}
        === EMAIL CONTEXT END ===

        User: {prompt}
        """

    elif task_type == "summarize":
        system_prompt = f"""
        You are an email summarization assistant.
        Read the following text or emails and summarize it in a short, professional summary (3–5 sentences max).
        Include key names, actions, and dates.

        Text to summarize:
        {prompt}
        """

    elif task_type == "report":
        system_prompt = f"""
            You are LensraMail, an AI email summarizer and assistant for {user.email}.
            Your goal is to create a short, professional report of the following email, write the report as though you are presenting as an assistant in the first person pov.
            The report will be sent to the user via WhatsApp, so keep it clear and concise.

        Data to report on:
        {prompt}
        """

    elif task_type == "classify":
        system_prompt = f"""
        You are an email classification model.
        Identify the intent or category of the provided email content.
        Choose from one of: ["personal", "business", "newsletter", "spam", "invitation", "event", "transaction", "other"].

        Respond in JSON:
        {{
            "category": "<chosen_category>",
            "reason": "<short explanation>"
        }}

        Email content:
        {prompt}
        """

    else:
        system_prompt = f"""
        You are LensraMail, a helpful assistant.
        The user said: "{prompt}".
        Respond appropriately in plain text.
        """

    # === STEP 4: Generate response ===
    model_instance = genai.GenerativeModel(model)
    response = model_instance.generate_content(system_prompt)

    # === STEP 5: Parse structured responses (JSON if possible) ===
    text = response.text.strip()
    try:
        clean_json = text.strip("```json").strip("```").strip()
        data = json.loads(clean_json)
        reply = data.get("reply", "")
        intent = data.get("intent", "none")
        required_fields = data.get("required_fields", {})
        fields = data.get("fields", {})
    except json.JSONDecodeError:
        data = {}
        reply = text
        intent = "none"
        required_fields = {}
        fields = {}

    # === STEP 6: Execute AI actions if relevant ===
    if intent != "none":
        print(f"Executing AI action: {intent}")
        execute_ai_action(user, data)

    # === STEP 7: Update memory for conversation continuity ===
    conversation_memory[user.id] = f"{prev_context}\nUser: {prompt}\nAI: {reply}"

    # === STEP 8: Return unified structured response ===
    return {
        "task_type": task_type,
        "intent": intent,
        "required_fields": required_fields,
        "fields": fields,
        "reply": reply,
        "timestamp": timezone.now().isoformat()
    }
