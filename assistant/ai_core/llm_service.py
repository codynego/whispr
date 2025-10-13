import json
from typing import Dict, Any, Optional, List
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from datetime import datetime


class LLMService:
    """
    Whispr’s core Gemini service.
    Handles contextual multi-turn conversations for:
    - Intent + entity detection
    - Missing info clarification
    - Reply generation after actions
    """
    # Class-level shared conversation history to persist across instances
    conversation_history: Dict[str, List[Dict[str, str]]] = {}

    def __init__(self, user, api_key: str, model_name: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model_obj = genai.GenerativeModel(model_name)
        self.model = model_name
        self.session_id = str(user.id)
        self.user = user

    def _json_serializable(self, obj):
        """Handle datetime serialization."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

    # --------------------------------------------------------
    # 1️⃣  MAINTAIN CONTEXT
    # --------------------------------------------------------
    def _get_context(self) -> str:
        """Retrieve only the last 1–2 messages for context."""
        history = self.conversation_history.get(self.session_id, [])
        # Keep only the last 2 messages
        recent_history = history[-4:]
        print("Recent History:", recent_history)
        formatted = "\n".join([f"{h['role'].capitalize()}: {h['content']}" for h in recent_history])
        return formatted or "(no prior context)"

    def _update_context(self, role: str, content: str):
        """Save each turn to the conversation history."""
        print(f"Updating context for session {self.session_id}: {role} -> {content}")
        if self.session_id not in self.conversation_history:
            self.conversation_history[self.session_id] = []
        self.conversation_history[self.session_id].append({"role": role, "content": content})
        print("Updated Conversation History:", self.conversation_history[self.session_id])


    def ask_for_missing_info(
        self,
        intent: str,
        missing_fields: list,
        entities: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a clarification question for missing entities,
        keeping context from prior messages.
        """
        context_text = self._get_context()
        prompt = f"""
You are Whispr’s AI assistant continuing a conversation.
Use the context below to sound natural and stay consistent.

Conversation so far:
{context_text}

Intent: {intent}
Missing fields: {', '.join(missing_fields)}
Known entities: {json.dumps(entities or {}, indent=2, default=self._json_serializable)}

Ask a short, friendly clarification question.
Example: "Who should I send it to?" or "Which email are you referring to?"
Respond with only the question.
        """

        response = self.model_obj.generate_content(prompt)
        text = response.text.strip()

        self._update_context("assistant", text)
        return text

    # --------------------------------------------------------
    # 4️⃣  REPLY GENERATION (after action)
    # --------------------------------------------------------
    def generate_reply(
        self,
        user_message: str,
        context_data: Dict[str, Any],
        task_result: Optional[Any] = None
    ) -> str:
        """
        Generate a conversational reply after performing a task,
        using session context.
        """
        context_text = self._get_context()
        
        prompt = f"""
        You are Whispr, the AI email assistant.
        Continue the conversation naturally, using past context and new data.

        Conversation so far:
        {context_text}

        User message: "{user_message}"
        Context data: {json.dumps(context_data, indent=2, default=self._json_serializable)}
        Task result: {json.dumps(task_result, indent=2, default=self._json_serializable) if task_result else "None"}

        Respond with a single, natural sentence.
        """
        print("LLM Reply Prompt:", prompt)

        response = self.model_obj.generate_content(prompt)
        text = response.text.strip()

        self._update_context("assistant", text)
        return text