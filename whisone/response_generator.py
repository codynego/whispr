from typing import List, Dict, Any
import openai  # Or your preferred GPT API

class ResponseGenerator:
    def __init__(self, openai_api_key: str, model: str = "gpt-5-mini"):
        openai.api_key = openai_api_key
        self.model = model

    def generate_response(self, user_message: str, executor_results: List[Dict[str, Any]]) -> str:
        """
        Generates a natural language response based on executor results.
        """
        import json
        executor_results_str = json.dumps(executor_results, indent=2, default=str)

        prompt = f"""
You are an AI assistant. A user sent the following message:
\"\"\"{user_message}\"\"\"

The system performed the following actions:
{executor_results_str}

Generate a concise, friendly, and informative summary for the user about what was done.
Do not include any JSON or code in your response.
"""
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes system actions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        content = response['choices'][0]['message']['content']
        return content
