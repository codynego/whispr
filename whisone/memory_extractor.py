from typing import Dict, Any, List
import openai
from datetime import datetime
import hashlib
import json
from django.conf import settings

class MemoryExtractor:
    """
    Extracts structured knowledge and user preferences from interactions, emails, and events.
    Stores metadata, entities, and context. Ensures preferences are well-structured.
    """

    DEFAULT_PREFERENCES = {
        "topics": [],                  # subjects the user is interested in
        "reminders": [],               # scheduled reminders
        "notifications": [],           # notification settings or preferences
        "language": "en",              # preferred language
        "timezone": "UTC",             # user timezone
        "likes": [],                   # things the user likes
        "dislikes": [],                # things the user dislikes
        "habits": [],                  # recurring behaviors or routines
        "interests": [],               # hobbies or areas of curiosity
        "priorities": [],              # high-priority items/tasks
        "communication_style": "neutral",  # preferred tone of communication
        "favorite_apps": [],           # apps or tools frequently used
        "shopping_preferences": {},    # categories, brands, or styles liked
        "dietary_preferences": {},     # food restrictions or favorites
        "travel_preferences": {},      # preferred locations, transport modes, hotels
        "learning_preferences": {},    # topics or formats the user prefers for learning
        "work_preferences": {},        # working hours, environment, tools
        "exercise_routine": {},        # workout preferences or schedules
        "social_preferences": {},      # preferred interaction style or groups
        "financial_preferences": {},   # budgeting or spending habits
        "health_preferences": {},      # general wellness or medical info
        "privacy_preferences": {},     # what info they want to keep private
        "reminder_styles": "default"   # e.g., concise, detailed, polite, casual
    }


    DEFAULT_ENTITIES = {"people": [], "companies": [], "topics": []}

    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def should_store(self, result: dict) -> bool:
        if not result:
            return False
        if isinstance(result, dict) and any(k in result for k in ["id", "content", "text", "task"]):
            return True
        return False

    def extract(self, content: str, source_type: str, timestamp: datetime = None) -> Dict[str, Any]:
        timestamp = timestamp or datetime.now()
        memory_id = self._generate_id(content, source_type, timestamp)

        structured_data = self._call_llm_extract(content)

        # Ensure preferences are always structured
        preferences = structured_data.get("preferences") or {}
        normalized_preferences = {**self.DEFAULT_PREFERENCES, **preferences}

        # Ensure entities are always structured
        entities = structured_data.get("entities") or self.DEFAULT_ENTITIES

        return {
            "id": memory_id,
            "source_type": source_type or "unknown",
            "timestamp": timestamp.isoformat(),
            "entities": entities,
            "preferences": normalized_preferences,
            "summary": structured_data.get("summary") or "No summary available"
        }

    def _call_llm_extract(self, content: str) -> Dict[str, Any]:
        prompt = (
            "You are an assistant that extracts important user context and preferences.\n\n"
            "The JSON format must be strictly followed and must not be empty.\n\n"
            "Return JSON with keys: entities, preferences, summary.\n"
            "Entities should include people, companies, topics.\n"
            "Preferences should include topics, reminders, notifications, language, timezone.\n"
            "Summary should be 1-2 concise sentences without sensitive data.\n\n"
            f"Content:\n\"\"\"{content}\"\"\""
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are Whisone, a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=500
        )

        response_text = response.choices[0].message.content.strip()
        if response_text.startswith("```") and response_text.endswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        try:
            data = json.loads(response_text)
            return {
                "entities": data.get("entities") or self.DEFAULT_ENTITIES,
                "preferences": data.get("preferences") or self.DEFAULT_PREFERENCES,
                "summary": data.get("summary") or "No summary available"
            }
        except json.JSONDecodeError:
            return {
                "entities": self.DEFAULT_ENTITIES,
                "preferences": self.DEFAULT_PREFERENCES,
                "summary": "No summary available"
            }

    def _generate_id(self, content: str, source_type: str, timestamp: datetime) -> str:
        raw = f"{source_type}|{timestamp.isoformat()}|{content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def merge_memories(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        merged_entities = []
        merged_preferences = dict(self.DEFAULT_PREFERENCES)
        merged_summary = []

        for mem in memories:
            merged_entities.extend(mem.get("entities", {}).get("people", []) +
                                   mem.get("entities", {}).get("companies", []) +
                                   mem.get("entities", {}).get("topics", []))
            merged_preferences.update(mem.get("preferences", {}))
            merged_summary.append(mem.get("summary", ""))

        # Ensure no duplicate entities
        merged_entities = list(set(merged_entities))

        return {
            "entities": {"people": merged_entities, "companies": [], "topics": []},  # could refine further
            "preferences": merged_preferences,
            "summary": " ".join(merged_summary)
        }
