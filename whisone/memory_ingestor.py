from typing import Dict, Any, List, Optional
from django.db import transaction
from django.utils import timezone
from .models import Entity, Fact, Relationship
import numpy as np
from difflib import SequenceMatcher

class MemoryIngestor:
    """
    Ingests structured memory dicts into Entity-Fact-Relationship KV.
    Supports:
    - Auto-update of existing entities/facts
    - Fact merging based on confidence
    - Relationship creation without duplicates
    - temp_id resolution
    - Name-based similarity matching to update existing entities
    """


    EMBEDDING_SIM_THRESHOLD = 0.85  
    NAME_SIM_THRESHOLD = 0.7  # similarity ratio for merging  

    def __init__(self, user):  
        self.user = user  

    def ingest(self, memory: Dict[str, Any], use_embedding_match: bool = False) -> Dict[str, Any]:  
        temp_id_map = {}  
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
    # Utility: get or create entity with fuzzy matching  
    # -----------------------  
    def _get_or_create_entity(self, name: str, type_: str, embedding: Optional[List[float]] = None) -> Entity:  
        # 1. Exact match by name/type  
        try:  
            entity = Entity.objects.get(user=self.user, name=name, type=type_)  
            if embedding and entity.embedding != embedding:  
                entity.embedding = embedding  
                entity.save(update_fields=["embedding", "updated_at"])  
            return entity  
        except Entity.DoesNotExist:  
            pass  

        # 2. Name similarity check  
        candidates = Entity.objects.filter(user=self.user, type=type_)  
        for e in candidates:  
            ratio = SequenceMatcher(None, e.name.lower(), name.lower()).ratio()  
            if ratio >= self.NAME_SIM_THRESHOLD:  
                # Update embedding if provided  
                if embedding:  
                    e.embedding = embedding  
                    e.save(update_fields=["embedding", "updated_at"])  
                return e  

        # 3. Optional: embedding similarity check  
        if embedding:  
            for e in candidates:  
                if e.embedding:  
                    sim = self._cosine_similarity(e.embedding, embedding)  
                    if sim > self.EMBEDDING_SIM_THRESHOLD:  
                        e.embedding = embedding  
                        e.save(update_fields=["embedding", "updated_at"])  
                        return e  

        # 4. Create new entity  
        entity = Entity.objects.create(user=self.user, name=name, type=type_, embedding=embedding)  
        return entity  

    @staticmethod  
    def _cosine_similarity(a: List[float], b: List[float]) -> float:  
        a, b = np.array(a), np.array(b)  
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:  
            return 0.0  
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))  

