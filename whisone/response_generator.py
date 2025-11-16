from typing import List, Dict, Any
import openai
import json
from assistant.models import AssistantMessage
from django.contrib.auth import get_user_model

User = get_user_model()





class ResponseGenerator:
    """
    Generates natural language responses based on conversation history,
    executor results, and optional vault context.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", history_limit: int = 1):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.history_limit = history_limit

    def generate_response(
        self,
        user: User,
        user_message: str,
        executor_results: List[Dict[str, Any]],
        vault_context: Dict[str, Any] = None
    ) -> str:
        # 1️⃣ Fetch recent conversation history
        history = AssistantMessage.objects.filter(user=user).order_by("-created_at")[:self.history_limit]
        history = reversed(history)  # Oldest first

        conversation_history = ""
        for msg in history:
            role = "User" if msg.role == "user" else "Assistant"
            conversation_history += f"{role}: {msg.content}\n"

        # 2️⃣ Serialize executor results
        executor_results_str = json.dumps(executor_results, indent=2, default=str)

        # 3️⃣ Serialize vault context if available
        vault_context_str = json.dumps(vault_context, indent=2, default=str) if vault_context else "None"

        # 4️⃣ Construct the prompt
        prompt = f"""
You are an AI assistant. Here's the conversation so far:
{conversation_history}

The user just sent the following message:
\"\"\"{user_message}\"\"\"

The system performed the following actions:
{executor_results_str}

Additional context from the user's knowledge vault:
{vault_context_str}

Generate a concise, friendly, and informative response for the user
about what was done and answer their message.
Do not include any JSON or code in your response.
"""

        # 5️⃣ Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes system actions and responds naturally."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        content = response.choices[0].message.content

        # 6️⃣ Optionally save the assistant's reply to AssistantMessage
        AssistantMessage.objects.create(user=user, role="assistant", content=content)

        return content
