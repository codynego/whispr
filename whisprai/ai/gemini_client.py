from .retriever import retrieve_relevant_emails
# from emails.tasks import send_email_task  # hypothetical Celery task to send emails
import google.generativeai as genai
from django.conf import settings
from django.utils import timezone
import json
from assistant.tasks import execute_ai_action  # to handle actions like sending email or setting reminders

genai.configure(api_key=settings.GEMINI_API_KEY)

# Simple per-user conversation cache (for follow-up context)
conversation_memory = {}

def get_gemini_response(prompt, user, model="gemini-2.0-flash", temperature=0.7, max_output_tokens=800):
    """
    Handles conversational and actionable requests using Gemini and user's email context.
    Supports:
    - Sending emails
    - Setting reminders
    - Replying to user questions
    Includes follow-up for missing required fields.
    """

    # === Step 1: Load previous conversation context ===
    prev_context = conversation_memory.get(user.id, "")

    # === Step 2: Retrieve relevant emails for grounding ===
    emails = retrieve_relevant_emails(user, prompt)
    email_context = "\n\n".join([
        f"From: {e.sender}\nSubject: {e.subject}\nBody: {e.body[:500]}..."
        for e in emails
    ]) or "No relevant emails found."

    # === Step 3: Build full system prompt ===
    full_prompt = f"""
    You are "LensraMail", an intelligent email assistant for {user.email}.
    You can analyze emails, answer questions, summarize conversations,
    and perform tasks such as drafting or sending emails, or setting reminders.

    Always respond in JSON with this structure:
    {{
        "intent": "<send_email|set_reminder|reply|none>",
        "required_fields": {{}},       # Include keys for any missing required fields
        "fields": {{}},                # Include all provided fields like 'to', 'subject', 'body', 'time'
        "reply": "<your textual assistant reply to the user>"
    }}

    Context from previous conversation:
    {prev_context}

    === EMAIL CONTEXT START ===
    {email_context}
    === EMAIL CONTEXT END ===

    User Query: {prompt}
    """

    # === Step 4: Generate response from Gemini ===
    model_instance = genai.GenerativeModel(model)
    response = model_instance.generate_content(full_prompt)

    # === Step 5: Parse JSON response ===
    try:
        data = json.loads(response.text.strip("```json").strip("```").strip())
        intent = data.get("intent", "none")
        required_fields = data.get("required_fields", {})
        fields = data.get("fields", {})
        reply = data.get("reply", response.text)
        print("Intent:", intent)
        print("Required fields:", required_fields)
        print("Provided fields:", fields)

        print("Executing action for intent:", intent)
        execute_ai_action(user, data)

        # Optional: trigger tasks if all required fields are provided
        # if intent == "send_email" and not required_fields:
        #     send_email_task.delay(user.id, fields.get("to"), fields.get("subject"), fields.get("body"))
        # elif intent == "set_reminder" and not required_fields:
        #     set_reminder_task.delay(user.id, fields.get("time"), fields.get("message"))

    except json.JSONDecodeError:
        # Treat as normal textual reply if JSON parsing fails
        intent = "none"
        required_fields = {}
        fields = {}
        reply = response.text

    # === Step 6: Update conversation memory for follow-ups ===
    conversation_memory[user.id] = f"{prev_context}\nUser: {prompt}\nAI: {reply}"

    # === Step 7: Return structured data for task processing ===
    return {
        "intent": intent,
        "required_fields": required_fields,
        "fields": fields,
        "reply": reply
    }
