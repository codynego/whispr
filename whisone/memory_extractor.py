from typing import Dict, Any, Optional
from datetime import datetime
import json
import openai
from django.conf import settings


class MemoryExtractor:
    """
    Extract structured memory aligned with the Memory Django model.
    DOES NOT save to DB.
    """

    def __init__(
        self,
        api_key: str = settings.OPENAI_API_KEY,
        model: str = "gpt-4o-mini"
    ):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def extract(
        self,
        content: str,
        previous_content: Optional[str] = None,
        source: str = "manual",
        timestamp: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Extract structured memory data from raw user content.
        Returns a dict ready to be passed to Memory(**data).
        """
        timestamp = timestamp or datetime.utcnow()

        structured = self._call_llm_extract(content, previous_content)

        return {
            "raw_text": content,
            "summary": structured.get("summary", "").strip() or "No summary extracted.",
            "memory_type": structured.get("memory_type", "reflection"),
            "emotion": structured.get("emotion"),
            "sentiment": structured.get("sentiment"),
            "importance": structured.get("importance", 0.5),
            "context": structured.get("context", {}),
            "source": source,
            "created_at": timestamp
        }

    # ------------------------
    # Internal helper
    # ------------------------
    def _call_llm_extract(self, content: str, previous_content: Optional[str] = None) -> Dict[str, Any]:
        # Combine previous context if available
        combined_content = ""
        if previous_content:
            combined_content = f"Previous messages for context:\n{previous_content}\n\n"
        combined_content += f"Current message:\n{content}"

        prompt = (
            "You are Whisone, an intelligent life-memory extraction system.\n\n"
            "Your task is to extract ONE structured memory from the user's message.\n\n"
            "Rules:\n"
            "1. Choose ONE memory_type from:\n"
            "   emotional, goal, learning, task, event, reflection, relationship\n"
            "2. If emotion is present, extract the dominant emotion.\n"
            "3. Sentiment must be a float between -1 and 1.\n"
            "4. Importance must be a float between 0 and 1 based on life relevance.\n"
            "5. Context MUST be an object using ONLY these keys:\n"
            "   topics, goals, blockers, people, recurring\n"
            "6. If a key has no values, return an empty list or false.\n"
            "7. Provide a clear 1–2 sentence summary.\n"
            "8. Return JSON ONLY. No explanations.\n\n"
            "Expected JSON format:\n"
            "{\n"
            '  "summary": "...",\n'
            '  "memory_type": "goal",\n'
            '  "emotion": "frustration",\n'
            '  "sentiment": -0.4,\n'
            '  "importance": 0.85,\n'
            '  "context": {\n'
            '    "topics": ["fitness"],\n'
            '    "goals": ["get fit"],\n'
            '    "blockers": ["fatigue"],\n'
            '    "people": [],\n'
            '    "recurring": true\n'
            "  }\n"
            "}\n\n"
            f"User messages (with recent context):\n{combined_content}\n"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You extract structured personal memories."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=500
        )

        response_text = response.choices[0].message.content.strip()

        # Remove code fences if present
        if response_text.startswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        try:
            data = json.loads(response_text)

            # Safety defaults
            data.setdefault("summary", "")
            data.setdefault("memory_type", "reflection")
            data.setdefault("emotion", None)
            data.setdefault("sentiment", None)
            data.setdefault("importance", 0.5)
            data.setdefault("context", {
                "topics": [],
                "goals": [],
                "blockers": [],
                "people": [],
                "recurring": False
            })

            return data

        except Exception as e:
            print("⚠️ Memory extraction failed:", e)
            return {
                "summary": "Memory could not be extracted.",
                "memory_type": "reflection",
                "emotion": None,
                "sentiment": None,
                "importance": 0.3,
                "context": {
                    "topics": [],
                    "goals": [],
                    "blockers": [],
                    "people": [],
                    "recurring": False
                }
            }
