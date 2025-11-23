from typing import Dict, Any, List, Optional
import openai
from datetime import datetime
import uuid
from django.conf import settings
from .models import Entity, Fact, Relationship
from django.db import transaction
from django.contrib.auth import get_user_model
import numpy as np

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
        summary = structured_data.get("summary", "")

        created_entities = []
        created_facts = []
        created_relationships = []

        with transaction.atomic():
            # Process entities
            for ent in entities_data:
                entity_obj = self._get_or_create_entity(user, ent)
                created_entities.append(entity_obj)

                # Process facts for this entity
                for key, value_conf in ent.get("facts", {}).items():
                    value = value_conf.get("value")
                    confidence = value_conf.get("confidence", 1.0)
                    fact_obj = self._create_or_update_fact(entity_obj, key, value, confidence)
                    created_facts.append(fact_obj)

            # Process relationships
            for rel in relationships_data:
                source_ent = self._find_entity_by_temp_id(created_entities, rel.get("from"))
                target_ent = self._find_entity_by_temp_id(created_entities, rel.get("to"))
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
            "Extract structured memory from the user's content.\n\n"
            "Return JSON ONLY with keys:\n"
            "* entities\n"
            "* relationships\n"
            "* summary\n\n"
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
            "Summary: 1-2 sentences describing the content.\n\n"
            f"Content:\n{content}\n"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are Whisone, a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=600
        )

        response_text = response.choices[0].message.content.strip()
        print("LLM Extraction Response:", response_text)

        # Remove code fences if present
        if response_text.startswith("```") and response_text.endswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        try:
            return json.loads(response_text)
        except Exception:
            return {"entities": [], "relationships": [], "summary": ""}

    def _get_or_create_entity(self, user, entity_data: Dict[str, Any]) -> Entity:
        """
        Check Knowledge Vault for existing entity by embedding similarity or name.
        If found, return existing entity. Otherwise create a new one.
        """
        name = entity_data.get("name")
        ent_type = entity_data.get("type", "unknown")
        embedding = entity_data.get("embedding")  # optional embedding from LLM

        # Search by name first
        existing = Entity.objects.filter(user=user, type=ent_type, name=name).first()
        if existing:
            return existing

        # Optional: implement embedding similarity check if embedding is provided
        # (for now, we skip, but could add vector similarity here)

        # Create new entity
        new_entity = Entity.objects.create(user=user, type=ent_type, name=name, embedding=embedding)
        return new_entity

    def _create_or_update_fact(self, entity_obj: Entity, key: str, value: str, confidence: float = 1.0) -> Fact:
        """
        Create or update a fact for an entity.
        If the fact already exists and new confidence is higher, update it.
        """
        existing_fact = Fact.objects.filter(entity=entity_obj, key=key).first()
        if existing_fact:
            if confidence >= existing_fact.confidence:
                existing_fact.value = value
                existing_fact.confidence = confidence
                existing_fact.save()
            return existing_fact

        return Fact.objects.create(entity=entity_obj, key=key, value=value, confidence=confidence)

    def _create_relationship(self, user, source: Entity, target: Entity, relation_type: str) -> Relationship:
        """
        Create a relationship if it does not already exist.
        """
        existing = Relationship.objects.filter(user=user, source=source, target=target, relation_type=relation_type).first()
        if existing:
            return existing

        return Relationship.objects.create(user=user, source=source, target=target, relation_type=relation_type)

    def _find_entity_by_temp_id(self, entities: List[Entity], temp_id: str) -> Optional[Entity]:
        """
        Map the temporary LLM-generated ID to the actual Entity object
        """
        for ent in entities:
            if getattr(ent, "temp_id", None) == temp_id:
                return ent
        return None

