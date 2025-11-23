from typing import Dict, Any, List, Optional
import openai
from datetime import datetime
import json
from django.conf import settings
import uuid

class MemoryExtractor:
    """
    Extract structured memory from user content.
    Returns dictionaries for ingestion without saving anything to DB.
    """

    DEFAULT_ENTITY_TYPES = ["person", "event", "location", "preference", "object", "goal", "task", "emotion", "action"]

    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def extract(self, user, content: str, source_type: str = "message", timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Extract entities, facts, and relationships from content.
        Returns a dict ready for MemoryIngestor ingestion.
        """
        timestamp = timestamp or datetime.now()

        # Call LLM to parse content
        structured_data = self._call_llm_extract(content)

        # Ensure defaults
        entities_data = structured_data.get("entities", [])
        relationships_data = structured_data.get("relationships", [])
        summary = structured_data.get("summary", "").strip()
        if not summary:
            summary = "No summary could be extracted from the content."

        # Assign unique temp_ids if missing
        for i, ent in enumerate(entities_data, start=1):
            ent.setdefault("temp_id", f"e{i}")
            ent.setdefault("facts", {})

        return {
            "entities": entities_data,          # list of dicts
            "relationships": relationships_data,  # list of dicts
            "summary": summary
        }

    # ------------------------
    # Internal helper methods
    # ------------------------

    def _call_llm_extract(self, content: str) -> Dict[str, Any]:
        prompt = (
            "You are Whisone, an intelligent memory assistant.\n"
            "Extract structured memory from the user's content.\n\n"
            "Instructions:\n"
            "1. ALWAYS produce at least one entity, even if the content has no obvious entities. Use type 'unknown'.\n"
            "2. Assign a unique 'temp_id' to each entity (e.g., e1, e2, ...).\n"
            "3. Extract facts for each entity if possible; if no facts, return an empty object '{}'.\n"
            "4. Extract relationships between entities; if none, return an empty list '[]'.\n"
            "5. Provide a 1-2 sentence summary.\n"
            "6. Return JSON ONLY. DO NOT include explanations.\n\n"
            "Return JSON with keys:\n"
            " - entities\n"
            " - relationships\n"
            " - summary\n\n"
            "Entities schema example:\n"
            "[\n"
            "  {\n"
            '    "temp_id": "e1",\n'
            '    "type": "person",\n'
            '    "name": "Sandra",\n'
            '    "facts": {\n'
            '      "role": {"value": "maid of honor", "confidence": 0.95},\n'
            '      "reminder_time": {"value": "2025-11-19T09:00:00", "confidence": 0.9}\n'
            "    }\n"
            "  }\n"
            "]\n\n"
            "Relationships schema example:\n"
            "[\n"
            "  {\n"
            '    "from": "e1",\n'
            '    "relation_type": "attending",\n'
            '    "to": "e2"\n'
            "  }\n"
            "]\n\n"
            f"Content:\n{content}\n"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts structured memories."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=800
        )

        response_text = response.choices[0].message.content.strip()
        # Remove code fences if present
        if response_text.startswith("```") and response_text.endswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        try:
            data = json.loads(response_text)
            data.setdefault("entities", [])
            data.setdefault("relationships", [])
            data.setdefault("summary", "")
            for ent in data["entities"]:
                ent.setdefault("facts", {})
            return data
        except Exception as e:
            print("⚠️ LLM JSON parse error:", e)
            return {"entities": [{"temp_id": "e1", "type": "unknown", "name": "Unknown", "facts": {}}], "relationships": [], "summary": "No summary available."}
