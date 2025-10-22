from .retriever import retrieve_relevant_messages
import google.generativeai as genai
from django.conf import settings
from django.utils import timezone
import json
from assistant.tasks import execute_ai_action  # handle actual AI-triggered actions
from django.contrib.auth import get_user_model
from celery import shared_task

genai.configure(api_key=settings.GEMINI_API_KEY)

User = get_user_model()

# In-memory conversation state
conversation_memory = {}


def get_gemini_response(
    prompt,
    user_id,
    task_type="conversational",
    model="gemini-2.5-flash",
    temperature=0.7,
    max_output_tokens=800,
    channel=None,
):
    """
    Unified entry point for Gemini-based AI tasks.

    Handles:
        - conversational: chat, Q&A, or reasoning across messages
        - summarize: summarize text or thread
        - report: generate short professional reports
        - classify: categorize messages or emails
        - insights: extract structured AI insights (summary, next steps, people, orgs, etc.)

    Can auto-detect relevant channel if not provided.
    """
    user = User.objects.get(id=user_id)

    # === STEP 1: Load conversation memory ===
    prev_context = conversation_memory.get(user.id, "")

    # === STEP 2: Detect or default channel ===
    detected_channel = channel
    if not detected_channel:
        # try to infer channel name from text
        if any(x in prompt.lower() for x in ["email", "inbox", "thread", "gmail"]):
            detected_channel = "email"
        elif any(x in prompt.lower() for x in ["chat", "whatsapp", "message"]):
            detected_channel = "whatsapp"
        else:
            detected_channel = "all"

    # === STEP 3: Retrieve context (relevant messages) ===
    channel_context = ""
    try:
        messages = retrieve_relevant_messages(user, prompt, channel=detected_channel)
        channel_context = "\n\n".join(
            [f"From: {m.sender_name or m.sender}\nContent: {m.body or m.content}" for m in messages]
        ) or "No recent messages found."
    except Exception as e:
        channel_context = f"(Context retrieval failed: {e})"

    # === STEP 4: Build task-specific system prompt ===
    if task_type == "conversational":
        system_prompt = f"""
        You are Whisone — a unified AI assistant for {user.email}.
        You can analyze messages, summarize threads, and respond intelligently across email, WhatsApp, or any other connected channels.

        Always respond in JSON:
        {{
            "intent": "<send_email|set_reminder|reply|none>",
            "required_fields": {{}},
            "fields": {{}},
            "reply": "<short response for the user>"
        }}

        Channel: {detected_channel}
        Context from previous conversation:
        {prev_context}

        === CHANNEL CONTEXT START ===
        {channel_context}
        === CHANNEL CONTEXT END ===

        User said: {prompt}
        """

    elif task_type == "summarize":
        system_prompt = f"""
        You are an intelligent summarizer. Read the following and provide a clear summary in 3–5 sentences.
        Focus on key people, actions, and decisions.

        Text to summarize:
        {prompt}
        """

    elif task_type == "report":
        system_prompt = f"""
        You are Whisone — a professional assistant for {user.email}.
        Create a concise report suitable for WhatsApp delivery, written in a friendly but professional tone.
        Include summary and suggested action steps.

        Report on the following:
        {prompt}
        """

    elif task_type == "classify":
        system_prompt = f"""
        You are a classification model.
        Categorize this message or email into one of these: ["personal", "business", "newsletter", "spam", "event", "transaction", "other"].

        Respond in JSON:
        {{
            "category": "<chosen_category>",
            "reason": "<short explanation>"
        }}

        Message content:
        {prompt}
        """

    elif task_type == "insights":
        system_prompt = f"""
        You are Whisone Insights — an analytical AI designed to extract structured insights from messages or email threads.

        Analyze the provided content and return a structured JSON object in this format:
        {{
            "summary": "<short human-like summary>",
            "next_step": "<what action the user might take next>",
            "people": ["<name1>", "<name2>"],
            "organizations": ["<org1>", "<org2>"],
            "related_topics": ["<topic1>", "<topic2>"]
        }}

        Context:
        {channel_context}

        Data to analyze:
        {prompt}
        """

    else:
        system_prompt = f"You are a helpful assistant. The user said: {prompt}"

    # === STEP 5: Generate response ===
    model_instance = genai.GenerativeModel(model)
    response = model_instance.generate_content(
        system_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature, max_output_tokens=max_output_tokens
        ),
    )

    # === STEP 6: Parse JSON safely ===
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

    # === STEP 7: Execute actions if needed ===
    if intent != "none":
        try:
            execute_ai_action(user, data)
        except Exception as e:
            print(f"⚠️ AI action failed: {e}")

    # === STEP 8: Update user memory ===
    conversation_memory[user.id] = f"{prev_context}\nUser: {prompt}\nAI: {reply}"

    # === STEP 9: Return unified response ===
    return {
        "task_type": task_type,
        "channel": detected_channel,
        "intent": intent,
        "required_fields": required_fields,
        "fields": fields,
        "reply": reply,
        "raw": text,
        "timestamp": timezone.now().isoformat(),
    }
