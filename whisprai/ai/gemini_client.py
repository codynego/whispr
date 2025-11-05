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
    print("Generating Gemini response for user ID:", user_id)
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
        You are Whisone, the user's unified personal assistant for {user.email}.
        You manage and analyze conversations across multiple sources — email, WhatsApp, and chat — and you understand the user's intent, summarize content, and propose intelligent next steps.

        🔹 Your personality: polite, helpful, analytical, and proactive.
        🔹 Your tone: natural, human-like, and confident.
        🔹 Your format: always respond in **structured JSON** as shown below.

        Expected JSON response:
        {{
            "intent": "<send_email|reply|set_reminder|create_task|summarize|none>",
            "required_fields": {{
                "example": "receiver, time, etc."
            }},
            "fields": {{
                "example": "parsed or detected fields"
            }},
            "reply": "<human-friendly assistant message to the user — 1–3 sentences>"
        }}

        Use the context to reason clearly and provide a helpful action suggestion or reply.

        ---
        **Channel:** {detected_channel}
        **Previous context:** {prev_context}

        === RECENT CONTEXT ===
        {channel_context}
        === END CONTEXT ===

        💬 User message:
        {prompt}
        """


    elif task_type == "summarize":
        system_prompt = f"""
        You are Whisone — a structured summarization assistant.
        Your task is to create a **clean, professional bullet-point summary** from the text below.

        🧭 Guidelines:
        - Present the summary as **clear bullet points**.
        - Start with a one-sentence headline summary.
        - Highlight key **people**, **actions**, **decisions**, and **outcomes**.
        - Group related ideas logically.
        - Avoid filler or repetition.
        - End with a short "Next Steps" or "Main Takeaway" section if relevant.
        - if more than 1 item to summarize, summarize them in a clear and understandable manner

        --- TEXT TO SUMMARIZE ---
        {prompt}
        """


    elif task_type == "report":
        system_prompt = f"""
        You are Whisone — the user's intelligent reporting assistant.
        Generate a **friendly, short report** that feels conversational but insightful — as if it could be sent directly over WhatsApp or email.

        🧾 Your report should include:
        1. **Summary** — clear overview in 2–4 sentences.
        2. **Highlights** — bullet points of key updates, events, or issues.
        3. **Suggested Actions** — practical next steps for the user.
        4. **Tone:** professional, warm, and concise.

        --- CONTENT TO REPORT ON ---
        {prompt}
        """


    elif task_type == "classify":
        system_prompt = f"""
        You are Whisone — an intelligent classifier that categorizes user messages and emails.

        Analyze the message carefully and classify it into **one** of the following categories:
        ["personal", "business", "newsletter", "spam", "event", "transaction", "other"]

        🧠 Provide a short reasoning explaining your choice.

        Output only valid JSON:
        {{
            "category": "<chosen_category>",
            "reason": "<why this category fits>"
        }}

        --- MESSAGE CONTENT ---
        {prompt}
        """


    elif task_type == "insights":
        system_prompt = f"""
        You are Whisone Insights — an advanced AI designed to extract **structured, human-like insights** from messages, chats, or email threads.

        Analyze the content carefully and produce JSON in this format:
        {{
            "summary": "<concise natural-language summary>",
            "key_points": ["<bullet point 1>", "<bullet point 2>", "<bullet point 3>"],
            "next_steps": ["<recommended next action>", "<optional additional action>"],
            "people": ["<name1>", "<name2>"],
            "organizations": ["<org1>", "<org2>"],
            "topics": ["<theme1>", "<theme2>"]
        }}

        🧭 Guidelines:
        - Focus on clarity and real insight — what’s actually happening?
        - Detect names, companies, or recurring subjects.
        - Suggest realistic next steps based on context.

        --- CONTEXT ---
        {channel_context}

        --- DATA TO ANALYZE ---
        {prompt}
        """


    else:
        system_prompt = f"""
        You are Whisone — a smart and empathetic assistant helping {user.email}.
        The user said: "{prompt}"

        Respond helpfully, clearly, and with practical guidance.
        """


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
