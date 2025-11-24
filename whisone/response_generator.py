from typing import List, Dict, Any
import json
import openai
import re
import logging
from django.contrib.auth import get_user_model
from assistant.models import AssistantMessage

logger = logging.getLogger(__name__)
User = get_user_model()


def clean_stars(text: str) -> str:
    """
    Converts **bold** into *italic* by removing one layer of asterisks.
    Leaves single asterisks untouched.
    """
    return re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)


class ResponseGenerator:
    """
    Generates natural-sounding responses using conversation history,
    executor outputs, memory vault context, and missing task fields.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", history_limit: int = 3):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.history_limit = history_limit

    def _build_conversation_history(self, user: User) -> str:
        messages = (
            AssistantMessage.objects
            .filter(user=user)
            .order_by("-created_at")[:self.history_limit]
        )
        messages = reversed(messages)  # oldest first

        history_str = ""
        for msg in messages:
            speaker = "User" if msg.role == "user" else "Assistant"
            history_str += f"{speaker}: {msg.content}\n"

        return history_str

    def _serialize(self, data: Any) -> str:
        try:
            return json.dumps(data, indent=2, default=str)
        except Exception:
            return str(data)

    def generate_response(
        self,
        user: User,
        user_message: str,
        executor_results: List[Dict[str, Any]],
        vault_context: Dict[str, Any] = None,
        missing_fields: List[List[str]] = None
    ) -> str:

        # 1️⃣ Build conversation history
        conversation_history = self._build_conversation_history(user)

        # 2️⃣ Serialize runtime data
        executor_results_str = self._serialize(executor_results)
        vault_context_str = self._serialize(vault_context) if vault_context else "None"

        # 3️⃣ Build missing-fields prompt
        missing_prompt = ""
        if missing_fields:
            flat = [item for group in missing_fields for item in group if item]
            if flat:
                missing_prompt = (
                    "Some information is missing to complete your request: "
                    f"{', '.join(flat)}. "
                    "Please ask the user in a friendly way to provide these details."
                )

        # 4️⃣ Build LLM prompt
        prompt = f"""
You are Whisone — a warm, relatable digital assistant who talks like a close friend:
casual, supportive, concise, clear, and slightly emotive (light emojis only when fitting).

Your goals:
• Understand the user’s message  
• Reference their history and vault context if relevant  
• Summarize actions taken by the system  
• Ask for any missing information  
• Avoid JSON or code  
• Keep responses friendly and human

Conversation so far:
{conversation_history}

User message:
\"\"\"{user_message}\"\"\"

System actions/results:
{executor_results_str}

Knowledge Vault context:
{vault_context_str}

{missing_prompt}

Using all of the above, write a natural response to the user.
"""

        # 5️⃣ Call OpenAI
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Whisone — warm, conversational, and human-like. "
                        "Sound like a supportive friend. Be concise and helpful."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        output = response.choices[0].message.content
        output = clean_stars(output)

        # 6️⃣ Save response
        try:
            AssistantMessage.objects.create(
                user=user,
                role="assistant",
                content=output
            )
        except Exception as e:
            logger.error(f"Failed to save assistant message: {e}")

        return output
