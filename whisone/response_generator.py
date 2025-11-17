from typing import List, Dict, Any
import openai
import json
from assistant.models import AssistantMessage
from django.contrib.auth import get_user_model
from .models import UserPreference

User = get_user_model()


class ResponseGenerator:
    """
    Generates natural language responses based on conversation history,
    executor results, optional vault context, and missing task parameters.
    Responses are tailored to feel more human-like and incorporate user preferences.
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
        preferences = UserPreference.objects.filter(user=user).first()

        conversation_history = ""
        for msg in history:
            role = "User" if msg.role == "user" else "Assistant"
            conversation_history += f"{role}: {msg.content}\n"

        # 2️⃣ Serialize executor results
        executor_results_str = json.dumps(executor_results, indent=2, default=str)

        # 3️⃣ Serialize vault context if available
        vault_context_str = json.dumps(vault_context, indent=2, default=str) if vault_context else "None"

        # 4️⃣ Serialize user preferences if available
        preferences_str = json.dumps(preferences.preferences if preferences else {}, indent=2, default=str)

        # 5️⃣ Handle missing fields
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

        # 6️⃣ Construct the prompt
        prompt = f"""
You are a friendly, human-like assistant—think of yourself as a helpful friend who's always got your back. Respond in a casual, natural way: use contractions, emojis sparingly if it fits, and keep it warm and empathetic. Tailor your tone and suggestions to the user's preferences, like their interests in topics (e.g., car maintenance or work-related notes), communication style (e.g., neutral), and any other details provided.

User preferences to consider:
{preferences_str}

Here's the conversation so far:
{conversation_history}

The user just sent the following message:
\"\"\"{user_message}\"\"\"

The system performed the following actions:
{executor_results_str}

Additional context from the user's knowledge vault:
{vault_context_str}

{missing_prompt}

Craft a concise, engaging response that chats naturally about what happened, answers their question, and gently follows up on anything needed. Make it feel like a real conversation—no stiff language, JSON, or code here.
"""

        # 7️⃣ Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a warm, relatable assistant who talks like a close friend—casual, supportive, and fun. "
                        "Weave in user preferences seamlessly to make responses feel personalized. Always aim for brevity "
                        "while being helpful and human."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7  # Slightly higher for more natural, varied responses
        )

        content = response.choices[0].message.content

        # 8️⃣ Save assistant reply to AssistantMessage
        print("Saving assistant message to DB")
        try:
            print("Saving assistant message to DB")
            AssistantMessage.objects.create(user=user, role="assistant", content=content)
        except Exception as e:
            logger.error(f"Error saving assistant message: {str(e)}")

        return content