from typing import List, Dict, Any, Optional
from django.utils import timezone
from django.db.models import Q
from .models import Entity, Fact, Relationship
import openai
import numpy as np

class KVQueryManager:
    """
    Hybrid query manager for Entity-Fact-Relationship KV.
    Combines structured filtering and semantic search for LLM context retrieval.
    """


    def __init__(self, user):
        self.user = user

    # -------------------------
    # Main query method
    # -------------------------
    def query(
        self,
        keyword: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        entity_names: Optional[List[str]] = None,
        fact_filters: Optional[List[Dict[str, Any]]] = None,
        relationship_filters: Optional[List[Dict[str, Any]]] = None,
        time_filters: Optional[List[Dict[str, Any]]] = None,
        limit: int = 5,
        use_semantic: bool = True
    ) -> List[Dict[str, Any]]:

        entities = Entity.objects.filter(user=self.user)

        # -------------------------
        # 1. Filter by entity type/name
        # -------------------------
        if entity_types:
            entities = entities.filter(type__in=entity_types)
        if entity_names:
            entities = entities.filter(name__in=entity_names)

        # -------------------------
        # 2. Filter by fact key/value or time
        # -------------------------
        if fact_filters:
            for f in fact_filters:
                key, value = f.get("key"), f.get("value")
                entities = entities.filter(facts__key=key, facts__value=value)

        if time_filters:
            for tf in time_filters:
                key, after, before = tf.get("key"), tf.get("after"), tf.get("before")
                q = Q()
                if after:
                    q &= Q(facts__key=key, facts__value__gte=after)
                if before:
                    q &= Q(facts__key=key, facts__value__lte=before)
                entities = entities.filter(q)

        entities = list(entities)

        # -------------------------
        # 3. Filter by relationships
        # -------------------------
        if relationship_filters:
            for rf in relationship_filters:
                relation_type = rf.get("relation_type")
                target_name = rf.get("target_name")
                rel_query = Relationship.objects.filter(
                    user=self.user,
                    relation_type=relation_type,
                    source__in=entities
                )
                if target_name:
                    rel_query = rel_query.filter(target__name=target_name)
                source_ids = rel_query.values_list("source_id", flat=True)
                entities = [e for e in entities if e.id in source_ids]

        # -------------------------
        # 4. Semantic search
        # -------------------------
        if keyword and use_semantic and entities:
            client = openai.OpenAI()
            try:
                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=keyword
                )
                query_embedding = response.data[0].embedding
            except Exception:
                query_embedding = None

            if query_embedding:
                def cosine(a, b):
                    a, b = np.array(a), np.array(b)
                    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
                        return 0.0
                    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

                scored_entities = []
                for ent in entities:
                    text_vec = ent.embedding
                    if not text_vec:
                        fact_values = [f.value for f in ent.facts.all()]
                        text_for_embedding = (ent.name or "") + " " + " ".join(fact_values)
                        try:
                            emb_resp = client.embeddings.create(
                                model="text-embedding-3-small",
                                input=text_for_embedding
                            )
                            text_vec = emb_resp.data[0].embedding
                            ent.embedding = text_vec
                            ent.save(update_fields=["embedding"])
                        except Exception:
                            continue
                    sim = cosine(query_embedding, text_vec)
                    scored_entities.append((sim, ent))
                scored_entities.sort(key=lambda x: x[0], reverse=True)
                entities = [e for sim, e in scored_entities[:limit]]
            else:
                entities = entities[:limit]
        else:
            entities = entities[:limit]

        # -------------------------
        # 5. Build result dicts
        # -------------------------
        results = []
        now = timezone.now()
        for ent in entities:
            facts_dict = {f.key: {"value": f.value, "confidence": f.confidence} for f in ent.facts.all()}
            relationships = []
            for rel in ent.source_rels.all():
                relationships.append({
                    "relation_type": rel.relation_type,
                    "target_id": str(rel.target.id),
                    "target_name": rel.target.name
                })
            ent.last_accessed = now
            ent.save(update_fields=["updated_at"])
            results.append({
                "entity_id": str(ent.id),
                "name": ent.name,
                "type": ent.type,
                "facts": facts_dict,
                "relationships": relationships,
                "created_at": ent.created_at.isoformat(),
                "updated_at": ent.updated_at.isoformat()
            })

        return results

