from typing import Dict, Any, List, Optional
import openai
from datetime import datetime
import uuid
from django.conf import settings
from .models import Entity, Fact, Relationship
from django.db import transaction
import json

class MemoryExtractor:
    """
    Extract structured memory from user content.
    Produces Entity, Fact, and Relationship objects ready for Knowledge Vault.
    """

    DEFAULT_ENTITY_TYPES = ["person", "event", "location", "preference", "object", "goal", "task", "emotion", "action"]

    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def extract(self, user, content: str, source_type: str = "message", timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Extract entities, facts, and relationships from content.
        Automatically checks Knowledge Vault for existing entities to merge/update.
        """
        timestamp = timestamp or datetime.now()

        # Call LLM to parse content
        structured_data = self._call_llm_extract(content)

        entities_data = structured_data.get("entities", [])
        relationships_data = structured_data.get("relationships", [])
        summary = structured_data.get("summary", "").strip()

        if not summary:
            summary = "No summary could be extracted from the content."

        created_entities = []
        created_facts = []
        created_relationships = []

        # In-memory temp_id mapping
        temp_id_map = {}

        with transaction.atomic():
            # Process entities
            for ent in entities_data:
                entity_obj = self._get_or_create_entity(user, ent)
                created_entities.append(entity_obj)
                temp_id_map[ent.get("temp_id")] = entity_obj

                # Process facts for this entity
                for key, value_conf in ent.get("facts", {}).items():
                    value = value_conf.get("value")
                    confidence = value_conf.get("confidence", 1.0)
                    fact_obj = self._create_or_update_fact(entity_obj, key, value, confidence)
                    created_facts.append(fact_obj)

            # Process relationships
            for rel in relationships_data:
                source_ent = temp_id_map.get(rel.get("from"))
                target_ent = temp_id_map.get(rel.get("to"))
                if source_ent and target_ent:
                    rel_obj = self._create_relationship(user, source_ent, target_ent, rel.get("relation_type"))
                    created_relationships.append(rel_obj)

        return {
            "entities": created_entities,
            "facts": created_facts,
            "relationships": created_relationships,
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
        print("LLM Extraction Response:", response_text)

        # Remove code fences if present
        if response_text.startswith("```") and response_text.endswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        try:
            data = json.loads(response_text)
            # Ensure keys exist
            data.setdefault("entities", [])
            data.setdefault("relationships", [])
            data.setdefault("summary", "")
            for ent in data["entities"]:
                ent.setdefault("facts", {})
            return data
        except Exception as e:
            print("⚠️ LLM JSON parse error:", e)
            return {"entities": [{"temp_id": "e1", "type": "unknown", "name": "Unknown", "facts": {}}], "relationships": [], "summary": summary}

    def _get_or_create_entity(self, user, entity_data: Dict[str, Any]) -> Entity:
        name = entity_data.get("name")
        ent_type = entity_data.get("type", "unknown")
        embedding = entity_data.get("embedding")

        # Search by name
        existing = Entity.objects.filter(user=user, type=ent_type, name=name).first()
        if existing:
            return existing

        # Create new entity
        new_entity = Entity.objects.create(user=user, type=ent_type, name=name, embedding=embedding)
        return new_entity

    def _create_or_update_fact(self, entity_obj: Entity, key: str, value: str, confidence: float = 1.0) -> Fact:
        existing_fact = Fact.objects.filter(entity=entity_obj, key=key).first()
        if existing_fact:
            if confidence >= existing_fact.confidence:
                existing_fact.value = value
                existing_fact.confidence = confidence
                existing_fact.save()
            return existing_fact

        return Fact.objects.create(entity=entity_obj, key=key, value=value, confidence=confidence)

    def _create_relationship(self, user, source: Entity, target: Entity, relation_type: str) -> Relationship:
        existing = Relationship.objects.filter(user=user, source=source, target=target, relation_type=relation_type).first()
        if existing:
            return existing

        return Relationship.objects.create(user=user, source=source, target=target, relation_type=relation_type)
