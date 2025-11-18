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
        "people": [],          # friends, family, colleagues, landlord
        "events": [],          # weddings, meetings, appointments, birthdays
        "tasks": [],           # to-dos, chores, bills
        "goals": [],           # long-term or short-term goals
        "preferences": {},     # likes, dislikes, habits, routines
        "meals": [],           # meals eaten, dietary info
        "shopping": [],        # shopping items, markets, stores
        "locations": [],       # places visited or important addresses
        "habits": [],          # recurring routines
        "social": [],          # social interactions, groups
        "financial": [],       # spending, savings, budgeting
        "health": [],          # exercise, wellness, medical info
        "learning": [],        # courses, topics, materials
        "work": [],            # projects, work environment, tasks
    }


    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def extract(self, content: str, source_type: str, timestamp: datetime = None) -> Dict[str, Any]:
        timestamp = timestamp or datetime.now()
        memory_id = self._generate_id(content, source_type, timestamp)

        structured_data = self._call_llm_extract(content)

        # Use extracted entities and relationships; fallback to defaults
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
        prompt = (
            "You are an assistant that extracts important user facts, events, tasks, goals, and preferences.\n\n"
            "Return JSON strictly with keys: entities, relationships, summary.\n"
            "- Entities may include people, events, tasks, goals, preferences.\n"
            "- Relationships should include 'from', 'relation', 'to' connecting entities.\n"
            "- Summary should be 1-2 concise sentences.\n\n"
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
        Deduplicates entities and relationships.
        """
        merged_entities = {
            "people": [],
            "events": [],
            "tasks": [],
            "goals": [],
            "preferences": {}
        }
        merged_relationships = []
        merged_summary = []

        for mem in memories:
            entities = mem.get("entities", {})
            merged_entities["people"].extend(entities.get("people", []))
            merged_entities["events"].extend(entities.get("events", []))
            merged_entities["tasks"].extend(entities.get("tasks", []))
            merged_entities["goals"].extend(entities.get("goals", []))
            merged_entities["preferences"].update(entities.get("preferences", {}))

            # Merge relationships
            merged_relationships.extend(mem.get("relationships", []))

            # Merge summaries
            merged_summary.append(mem.get("summary", ""))

        # Deduplicate entities
        for key in ["people", "events", "tasks", "goals"]:
            merged_entities[key] = list({json.dumps(e, sort_keys=True) for e in merged_entities[key]})
            merged_entities[key] = [json.loads(e) for e in merged_entities[key]]

        # Deduplicate relationships
        merged_relationships = list({json.dumps(r, sort_keys=True) for r in merged_relationships})
        merged_relationships = [json.loads(r) for r in merged_relationships]

        return {
            "entities": merged_entities,
            "relationships": merged_relationships,
            "summary": " ".join(merged_summary)
        }
