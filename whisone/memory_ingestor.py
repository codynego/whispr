from typing import Dict, Any, List, Optional
from django.db import transaction
from django.utils import timezone
from .models import Entity, Fact, Relationship
import uuid
import numpy as np

class MemoryIngestor:
    """
    Ingests structured memory from MemoryExtractor into the Entity-Fact-Relationship KV.
    Supports:
    - Auto-update of existing entities/facts
    - Fact merging based on confidence
    - Relationship creation without duplicates
    - temp_id resolution
    """

    def __init__(self, user):
        self.user = user

    def ingest(self, memory: Dict[str, Any], use_embedding_match: bool = False) -> Dict[str, Any]:
        """
        memory: {
            "entities": [ { "temp_id": "e1", "type": "person", "name": "Sandra", "facts": {...} } ],
            "relationships": [ {"from": "e1", "relation_type": "attending", "to": "e2"} ],
            "summary": "..."
        }
        """
        temp_id_map = {}  # Maps temp_id to actual Entity instance

        entities_data = memory.get("entities", [])
        relationships_data = memory.get("relationships", [])
        summary = memory.get("summary", "")

        stored_entities = []

        with transaction.atomic():
            # -----------------------
            # 1. Process Entities
            # -----------------------
            for ent_data in entities_data:
                temp_id = ent_data.get("temp_id")
                name = ent_data.get("name")
                type_ = ent_data.get("type", "unknown")
                embedding = ent_data.get("embedding") if use_embedding_match else None

                entity = self._get_or_create_entity(name, type_, embedding)
                temp_id_map[temp_id] = entity
                stored_entities.append(entity)

                # -----------------------
                # 2. Merge Facts
                # -----------------------
                facts = ent_data.get("facts", {})
                for key, val_dict in facts.items():
                    value = val_dict.get("value")
                    confidence = float(val_dict.get("confidence", 1.0))

                    fact_obj, created = Fact.objects.get_or_create(
                        entity=entity,
                        key=key,
                        defaults={"value": value, "confidence": confidence}
                    )
                    if not created:
                        # Update only if new value differs or higher confidence
                        if fact_obj.value != value or confidence > fact_obj.confidence:
                            fact_obj.value = value
                            fact_obj.confidence = confidence
                            fact_obj.save(update_fields=["value", "confidence", "updated_at"])

            # -----------------------
            # 3. Process Relationships
            # -----------------------
            for rel in relationships_data:
                from_temp = rel.get("from")
                to_temp = rel.get("to")
                relation_type = rel.get("relation_type", "related")

                source = temp_id_map.get(from_temp)
                target = temp_id_map.get(to_temp)

                if source and target:
                    # Avoid duplicate relationships
                    Relationship.objects.get_or_create(
                        user=self.user,
                        source=source,
                        target=target,
                        relation_type=relation_type
                    )

        return {
            "stored_entities": [e.id for e in stored_entities],
            "relationships_created": len(relationships_data),
            "summary": summary
        }

    # -----------------------
    # Utility: get or create entity (with optional embedding fuzzy match)
    # -----------------------
    def _get_or_create_entity(self, name: str, type_: str, embedding: Optional[List[float]] = None) -> Entity:
        """
        Returns an existing entity if name/type match or embedding similarity passes threshold.
        Else creates a new entity.
        """
        # Exact match by name/type
        try:
            entity = Entity.objects.get(user=self.user, name=name, type=type_)
            if embedding and entity.embedding != embedding:
                entity.embedding = embedding
                entity.save(update_fields=["embedding", "updated_at"])
            return entity
        except Entity.DoesNotExist:
            pass

        # Optional: embedding similarity check (fuzzy match)
        if embedding:
            all_entities = Entity.objects.filter(user=self.user, type=type_)
            for e in all_entities:
                if e.embedding:
                    sim = self._cosine_similarity(e.embedding, embedding)
                    if sim > 0.85:  # similarity threshold
                        e.embedding = embedding
                        e.save(update_fields=["embedding", "updated_at"])
                        return e

        # Create new entity
        entity = Entity.objects.create(
            user=self.user,
            name=name,
            type=type_,
            embedding=embedding
        )
        return entity

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        a, b = np.array(a), np.array(b)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

