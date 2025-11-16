from typing import Dict, Any, List
import openai
from datetime import datetime
import hashlib
import json
from django.conf import settings

class MemoryExtractor:
    """
    Extracts structured knowledge and user preferences from interactions, emails, and events.
    Does NOT store raw content. Instead, stores meaningful metadata, entities, and context.
    """

    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    # ---------------------------
    # Main entry point
    # ---------------------------
    def extract(self, content: str, source_type: str, timestamp: datetime = None) -> Dict[str, Any]:
        timestamp = timestamp or datetime.now()
        memory_id = self._generate_id(content, source_type, timestamp)

        structured_data = self._call_llm_extract(content)

        return {
            "id": memory_id,
            "source_type": source_type or "unknown",
            "timestamp": timestamp.isoformat(),
            "entities": structured_data.get("entities") or [],
            "preferences": structured_data.get("preferences") or {},
            "summary": structured_data.get("summary") or "No summary available"
        }


    # ---------------------------
    # LLM Extraction
    # ---------------------------
    def _call_llm_extract(self, content: str) -> Dict[str, Any]:
        prompt = (
            "You are an assistant that extracts important user context and preferences.\n\n"
            "The JSON format must be strictly followed and must not be empty.\n\n"
            "Extract the following as JSON:\n"
            "1. Entities mentioned (people, companies, topics).\n"
            "2. User preferences or intent indicated.\n"
            "3. A concise summary (1-2 sentences) without including raw sensitive info.\n\n"
            f"Content:\n\"\"\"{content}\"\"\"\n\n"
            "Return JSON only with keys: entities, preferences, summary."
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "yo are whisone, a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=500,
        )

        response_text = response.choices[0].message.content.strip()

        # Remove triple backticks if present
        if response_text.startswith("```") and response_text.endswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        try:
            data = json.loads(response_text)
            return {
                "entities": data.get("entities") or {"people": [], "companies": [], "topics": []},
                "preferences": data.get("preferences") or {},
                "summary": data.get("summary") or "No summary available"
            }
        except json.JSONDecodeError:
            # Fallback in case of parsing failure
            return {
                "entities": {"people": [], "companies": [], "topics": []},
                "preferences": {},
                "summary": "No summary available"
            }


    # ---------------------------
    # Generate unique memory ID
    # ---------------------------
    def _generate_id(self, content: str, source_type: str, timestamp: datetime) -> str:
        """
        Generate a unique hash ID for this memory entry.
        """
        raw = f"{source_type}|{timestamp.isoformat()}|{content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ---------------------------
    # Optional: Merge memories
    # ---------------------------
    def merge_memories(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple memory entries into a single context for easier querying.
        """
        merged_entities = []
        merged_preferences = {}
        merged_summary = []

        for mem in memories:
            merged_entities.extend(mem.get("entities", []))
            merged_preferences.update(mem.get("preferences", {}))
            merged_summary.append(mem.get("summary", ""))

        return {
            "entities": list(set(merged_entities)),
            "preferences": merged_preferences,
            "summary": " ".join(merged_summary),
        }
