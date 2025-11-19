from typing import Dict, Any, List
import openai
from datetime import datetime
import hashlib
import json
from django.conf import settings


class MemoryExtractor:
    """
    Extracts structured knowledge from user interactions, messages, or events.
    Produces entities and relationships suitable for the graph/tree knowledge vault.
    """

    DEFAULT_ENTITIES = {
        "people": [],
        "events": [],
        "tasks": [],
        "goals": [],
        "emotions": [],
        "actions": [],
        "preferences": {
            "likes": [],
            "dislikes": [],
            "routines": []
        },
        "locations": [],
        "objects": []
    }

    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def extract(self, content: str, source_type: str, timestamp: datetime = None) -> Dict[str, Any]:
        timestamp = timestamp or datetime.now()
        memory_id = self._generate_id(content, source_type, timestamp)

        structured_data = self._call_llm_extract(content)

        entities = structured_data.get("entities") or self.DEFAULT_ENTITIES
        relationships = structured_data.get("relationships") or []

        return {
            "id": memory_id,
            "source_type": source_type or "unknown",
            "timestamp": timestamp.isoformat(),
            "entities": entities,
            "relationships": relationships,
            "summary": structured_data.get("summary") or "No summary available"
        }

    def _call_llm_extract(self, content: str) -> Dict[str, Any]:

        prompt = f"""
Extract structured memory from the user's content.

Return JSON ONLY with keys:
- entities
- relationships
- summary

Entities must use this schema EXACTLY:

{{
  "people": [],
  "events": [],
  "tasks": [],
  "goals": [],
  "emotions": [],
  "actions": [],
  "preferences": {{
      "likes": [],
      "dislikes": [],
      "routines": []
  }},
  "locations": [],
  "objects": []
}}

Rules:
- Events = things that happened.
- Tasks = future to-dos or pending responsibilities.
- Actions = things the user actually performed.
- Emotions = feelings or moods.
- People = humans mentioned.
- Relationships MUST be of form: {{"from": "", "relation": "", "to": ""}}

Keep summary to 1–2 sentences.

Content:
\"\"\"{content}\"\"\"
"""

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

        # Strip code fences if present
        if response_text.startswith("```") and response_text.endswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        try:
            data = json.loads(response_text)
            return {
                "entities": data.get("entities") or self.DEFAULT_ENTITIES,
                "relationships": data.get("relationships") or [],
                "summary": data.get("summary") or "No summary available"
            }
        except json.JSONDecodeError:
            return {
                "entities": self.DEFAULT_ENTITIES,
                "relationships": [],
                "summary": "No summary available"
            }

    def _generate_id(self, content: str, source_type: str, timestamp: datetime) -> str:
        raw = f"{source_type}|{timestamp.isoformat()}|{content}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def merge_memories(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple memory entries into a single structured object.
        Deduplicate entities and relationships.
        """

        merged_entities = {
            "people": [],
            "events": [],
            "tasks": [],
            "goals": [],
            "emotions": [],
            "actions": [],
            "preferences": {
                "likes": [],
                "dislikes": [],
                "routines": []
            },
            "locations": [],
            "objects": []
        }

        merged_relationships = []
        merged_summary = []

        for mem in memories:
            entities = mem.get("entities", {})

            # Direct list merges
            for key in ["people", "events", "tasks", "goals", "emotions", "actions", "locations", "objects"]:
                merged_entities[key].extend(entities.get(key, []))

            # Preferences merge
            prefs = entities.get("preferences", {})
            merged_entities["preferences"]["likes"].extend(prefs.get("likes", []))
            merged_entities["preferences"]["dislikes"].extend(prefs.get("dislikes", []))
            merged_entities["preferences"]["routines"].extend(prefs.get("routines", []))

            # Merge relationships
            merged_relationships.extend(mem.get("relationships", []))

            # Merge summaries
            merged_summary.append(mem.get("summary", ""))

        # Deduplicate all list-based fields
        for key in ["people", "events", "tasks", "goals", "emotions", "actions", "locations", "objects"]:
            merged_entities[key] = list(set(merged_entities[key]))

        for pref in ["likes", "dislikes", "routines"]:
            merged_entities["preferences"][pref] = list(set(merged_entities["preferences"][pref]))

        # Deduplicate relationships
        merged_relationships = [json.loads(r) for r in set(json.dumps(r, sort_keys=True) for r in merged_relationships)]

        return {
            "entities": merged_entities,
            "relationships": merged_relationships,
            "summary": " ".join(merged_summary).strip()
        }
