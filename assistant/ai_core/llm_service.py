import json
from typing import Dict, Any, Optional, List
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from datetime import datetime


class LLMService:
    """
    🧠 Whispr’s Core Gemini Service
    Handles intelligent, contextual, multi-turn conversations for:
      - Intent & entity detection
      - Clarification of missing information
      - Natural follow-up and reply generation after actions or summaries

    Maintains lightweight conversation memory per user session.
    """

    # Shared in-memory conversation storage across sessions
    conversation_history: Dict[str, List[Dict[str, str]]] = {}

    def __init__(self, user, api_key: str, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model_obj = genai.GenerativeModel(model_name)
        self.model = model_name
        self.session_id = str(user.id)
        self.user = user

    # --------------------------------------------------------
    #  🔧 UTILITIES
    # --------------------------------------------------------
    def _json_serializable(self, obj):
        """Safely convert datetime and similar objects for JSON serialization."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    def _get_context(self, limit: int = 4) -> str:
        """Retrieve the most recent messages (last few turns) for conversation continuity."""
        history = self.conversation_history.get(self.session_id, [])
        recent = history[-limit:]
        return "\n".join([f"{h['role'].capitalize()}: {h['content']}" for h in recent]) or "(no prior context)"

    def _update_context(self, role: str, content: str):
        """Append a new conversational turn (user or assistant) to session memory."""
        if self.session_id not in self.conversation_history:
            self.conversation_history[self.session_id] = []
        self.conversation_history[self.session_id].append({"role": role, "content": content})

    # --------------------------------------------------------
    #  🗣️ CLARIFICATION PROMPTS
    # --------------------------------------------------------
    def ask_for_missing_info(
        self,
        intent: str,
        missing_fields: list,
        entities: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a friendly, context-aware clarification question
        when required details are missing from the user's message.
        Example output:
          - "Who should I send it to?"
          - "What time would you like me to schedule it for?"
        """
        context_text = self._get_context()
        prompt = f"""
You are **Whisone**, a helpful, context-aware assistant.

Your goal is to ask a **short, natural question** that helps fill in missing information for the current intent.

🧩 Conversation so far:
{context_text}

🎯 Intent: {intent}
❗ Missing fields: {', '.join(missing_fields)}
📍 Known entities:
{json.dumps(entities or {}, indent=2, default=self._json_serializable)}

Respond with ONE friendly question only — no explanations, no greetings.
Be conversational and adaptive to context tone.
"""
        response = self.model_obj.generate_content(prompt)
        reply = response.text.strip()
        self._update_context("assistant", reply)
        return reply

    # --------------------------------------------------------
    #  💬 REPLY GENERATION (After Task Completion)
    # --------------------------------------------------------
    def generate_reply(
        self,
        user_message: str,
        context_data: Dict[str, Any],
        task_result: Optional[Any] = None,
        detected_channel: Optional[str] = None
    ) -> str:
        """
        Generate a natural, intelligent response after executing a task
        (e.g., sending an email, summarizing content, or providing insights).

        Automatically adjusts tone based on the detected communication channel:
          - 📧 Email → Polished and professional
          - 💬 Chat → Friendly and conversational
          - 🌐 Default → Neutral and concise
        """
        context_text = self._get_context()

        # Channel-adaptive style tone
        tone_style = {
            "email": "Use a professional, polished assistant tone.",
            "chat": "Use a casual, conversational tone — short and friendly.",
        }.get(detected_channel, "Use a clear, neutral tone suitable for general responses.")

        prompt = f"""
You are **Whisone**, an intelligent assistant that helps users manage and summarize their communication data.

{tone_style}

🧠 Previous context:
{context_text}

💬 User message:
"{user_message}"

📨 Context or retrieved data:
{json.dumps(context_data, indent=2, default=self._json_serializable)}

📂 Task result (if available):
{json.dumps(task_result, indent=2, default=self._json_serializable) if task_result else "None"}

Instructions:
- Reply in 1–2 short sentences.
- Be direct, factual, and clear.
- Avoid generic phrases like “I’ll check that for you.”
- For summaries → give a clean summary sentence.
- For counts or lists → give numbers or concise overviews.
- For confirmed actions → affirm completion naturally.
- For mixed insights → synthesize key highlights only.
"""
        response = self.model_obj.generate_content(prompt)
        reply = response.text.strip()
        self._update_context("assistant", reply)
        return reply
