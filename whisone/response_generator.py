from typing import List, Dict, Any
import openai
import json
from assistant.models import AssistantMessage
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class ResponseGenerator:
    """
    Generates human-like responses based on conversation history,
    executor results, optional vault context, and missing task parameters.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", history_limit: int = 3):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.history_limit = history_limit

    def generate_response(
        self,
        user: User,
        user_message: str,
        executor_results: List[Dict[str, Any]],
        vault_context: Dict[str, Any] = None,
        missing_fields: List[List[str]] = None
    ) -> str:
        # 1️⃣ Fetch recent conversation history
        history_qs = AssistantMessage.objects.filter(user=user).order_by("-created_at")[:self.history_limit]
        history = reversed(history_qs)  # Oldest first

        conversation_history = ""
        for msg in history:
            role = "User" if msg.role == "user" else "Assistant"
            conversation_history += f"{role}: {msg.content}\n"

        # 2️⃣ Serialize executor results
        executor_results_str = json.dumps(executor_results, indent=2, default=str)

        # 3️⃣ Serialize vault context if available
        vault_context_str = json.dumps(vault_context, indent=2, default=str) if vault_context else "None"

        # 4️⃣ Handle missing fields
        missing_prompt = ""
        if missing_fields:
            flat_missing = [field for sublist in missing_fields for field in sublist if field]
            if flat_missing:
                missing_prompt = (
                    "Some information is missing to complete certain tasks: "
                    f"{', '.join(flat_missing)}. "
                    "Ask the user politely to provide these values so the tasks can be completed."
                )

        # 5️⃣ Construct prompt
        prompt = f"""
You are a friendly, human-like assistant—think of yourself as a helpful friend who's always got the user's back. Respond in a casual, warm way, use contractions, and sprinkle emojis sparingly if appropriate.

Conversation so far:
{conversation_history}

User message:
\"\"\"{user_message}\"\"\"

System actions/results:
{executor_results_str}

Knowledge Vault context:
{vault_context_str}

{missing_prompt}

Craft a concise, engaging response that feels like a real conversation—answer questions, summarize actions taken, and follow up on missing information if any. No JSON or code in the response.
"""

        # 6️⃣ Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a warm, relatable assistant who talks like a close friend—casual, supportive, and helpful. "
                        "Be concise and friendly."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        content = response.choices[0].message.content

        # 7️⃣ Save assistant reply
        try:
            AssistantMessage.objects.create(user=user, role="assistant", content=content)
        except Exception as e:
            logger.error(f"Error saving assistant message: {str(e)}")

        return content
