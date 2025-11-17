from typing import List, Dict, Any
import openai
import json
from assistant.models import AssistantMessage
from django.contrib.auth import get_user_model

User = get_user_model()


class ResponseGenerator:
    """
    Generates natural language responses based on conversation history,
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
            # Flatten list of missing fields
            flat_missing = [field for sublist in missing_fields for field in sublist if field]
            if flat_missing:
                missing_prompt = (
                    "Also, some information is missing to complete certain tasks: "
                    f"{', '.join(flat_missing)}. "
                    "Ask the user politely to provide these values so the tasks can be completed."
                )

        # 5️⃣ Construct the prompt
        prompt = f"""
You are an AI assistant. Here's the conversation so far:
{conversation_history}

The user just sent the following message:
\"\"\"{user_message}\"\"\"

The system performed the following actions:
{executor_results_str}

Additional context from the user's knowledge vault:
{vault_context_str}

{missing_prompt}

Generate a concise, friendly, and informative response to the user
about what was done, answer their message, and if applicable, ask for any missing information politely.
Do not include JSON or code in your response.
"""

        # 6️⃣ Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes system actions, responds naturally, "
                               "and asks the user for missing information if needed."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        content = response.choices[0].message.content

        # 7️⃣ Save assistant reply to AssistantMessage
        AssistantMessage.objects.create(user=user, role="assistant", content=content)

        return content
