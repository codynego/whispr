from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q
from .models import KnowledgeVaultEntry
import uuid
import openai
import numpy as np
from celery import shared_task





@shared_task
def generate_embedding_task(entry_id: str):
    entry = KnowledgeVaultEntry.objects.get(id=entry_id)
    client = openai.OpenAI()

    # Build text for embedding
    text_search = entry.text_search or entry.summary
    if not text_search:
        return

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text_search
    )
    embedding = response.data[0].embedding

    # Save embedding
    entry.embedding = embedding
    entry.save(update_fields=["embedding"])




class KnowledgeVaultManager:
    """
    Knowledge Vault Manager with async embedding ingestion and semantic search.
    Implements:
    - Sparse checks to avoid ingesting empty/irrelevant memories
    - Updating memories
    - Semantic query
    - Fetch recent memories
    - Prune old memories
    """

    def __init__(self, user):
        self.user = user

    # ---------------------------
    # Utility: Build searchable text
    # ---------------------------
    def _build_text_search(
        self, summary: str, entities: Dict[str, Any], relationships: List[Dict[str, str]]
    ) -> str:
        parts = [summary]
        for key, values in entities.items():
            if isinstance(values, list) and values:
                parts.append(" ".join(map(str, values)))
        for rel in relationships:
            if isinstance(rel, dict):
                parts.append(" ".join(rel.values()))
        return " ".join(parts)

    # ---------------------------
    # 1️⃣ Ingest Memory (async embedding)
    # ---------------------------
    def ingest_memory(
        self,
        content: str,
        entities: Dict[str, Any],
        relationships: List[Dict[str, str]],
        summary: str
    ) -> Optional[KnowledgeVaultEntry]:
        """
        Add a memory only if it passes sparsity checks.
        Embedding is generated asynchronously in the background.
        Returns None if memory is skipped.
        """
        # ---------------------------
        # 1️⃣ Basic sanity checks
        # ---------------------------
        if not summary or len(summary.strip()) < 10:
            return None
        if not content or len(content.strip()) < 5:
            return None

        meaningful_entities_count = sum(
            len(v) for v in entities.values() if isinstance(v, list) and len(v) > 0
        )
        meaningful_relationships_count = len(relationships) if relationships else 0
        total_meaningful = meaningful_entities_count + meaningful_relationships_count

        if total_meaningful < 2:
            # Skip sparse memories
            return None

        # ---------------------------
        # 2️⃣ Build searchable text
        # ---------------------------
        text_search = self._build_text_search(summary, entities, relationships)

        # ---------------------------
        # 3️⃣ Save memory without embedding
        # ---------------------------
        memory_id = str(uuid.uuid4())
        entry = KnowledgeVaultEntry.objects.create(
            user=self.user,
            memory_id=memory_id,
            summary=summary,
            entities=entities,
            relationships=relationships,
            text_search=text_search,
            timestamp=timezone.now()
        )

        # ---------------------------
        # 4️⃣ Queue embedding generation asynchronously
        # ---------------------------
        generate_embedding_task.delay(str(entry.id))

        return entry

    # ---------------------------
    # 2️⃣ Update Memory (async embedding)
    # ---------------------------
    def update_memory(
        self,
        memory_id: str,
        entities: Optional[Dict[str, Any]] = None,
        relationships: Optional[List[Dict[str, str]]] = None,
        summary: Optional[str] = None
    ) -> Optional[KnowledgeVaultEntry]:
        try:
            entry = KnowledgeVaultEntry.objects.get(user=self.user, memory_id=memory_id)
        except KnowledgeVaultEntry.DoesNotExist:
            return None

        if entities:
            for key, value in entities.items():
                existing = entry.entities.get(key, [])
                if isinstance(existing, list) and isinstance(value, list):
                    entry.entities[key] = list(set(existing + value))
                else:
                    entry.entities[key] = value

        if relationships:
            entry.relationships = list(set(entry.relationships + relationships))

        if summary:
            entry.summary = summary
            entry.text_search = self._build_text_search(summary, entry.entities, entry.relationships)
            generate_embedding_task.delay(str(entry.id))

        entry.last_accessed = timezone.now()
        entry.save()
        return entry

    # ---------------------------
    # 3️⃣ Query Memory (semantic + filters)
    # ---------------------------
    def query(
        self,
        keyword: Optional[str] = None,
        entities: Optional[List[str]] = None,
        relationships: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:

        # Base entries
        entries = KnowledgeVaultEntry.objects.filter(user=self.user)

        # ---- ENTITY FILTERS ----
        if entities:
            q = Q()
            for e in entities:
                q |= Q(**{f"entities__{e}__isnull": False})
            entries = entries.filter(q)

        # ---- RELATIONSHIP FILTERS ----
        if relationships:
            for r in relationships:
                entries = entries.filter(relationships__icontains=r)

        # ---- TIME FILTERS ----
        if filters:
            for f in filters:
                key, value = f.get("key"), f.get("value")
                if key == "after":
                    entries = entries.filter(timestamp__gte=value)
                elif key == "before":
                    entries = entries.filter(timestamp__lte=value)

        # ---- KEYWORD FILTER (TEXT SEARCH ONLY) ----
        if keyword:
            entries = entries.filter(
                Q(summary__icontains=keyword) |
                Q(relationships__icontains=keyword)
            )

        # Limit result count early
        entries = entries.order_by("-timestamp")[:limit]

        # ---- UPDATE LAST ACCESSED ----
        now = timezone.now()
        for e in entries:
            e.last_accessed = now
            e.save(update_fields=["last_accessed"])

        # ---- RETURN DICTS ----
        results = []
        for e in entries:
            results.append({
                "memory_id": str(e.memory_id),
                "summary": e.summary,
                "entities": e.entities,
                "relationships": e.relationships,
                "timestamp": e.timestamp.isoformat(),
                "last_accessed": e.last_accessed.isoformat()
            })

        return results



    # ---------------------------
    # 4️⃣ Fetch Recent Memories
    # ---------------------------
    def recent_memories(self, limit: int = 5):
        entries = KnowledgeVaultEntry.objects.filter(user=self.user).order_by("-timestamp")[:limit]
        for entry in entries:
            entry.last_accessed = timezone.now()
            entry.save(update_fields=["last_accessed"])
        return list(entries)

    # ---------------------------
    # 5️⃣ Prune Old Memories
    # ---------------------------
    def prune_old_memory(self, days: int = 90):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        KnowledgeVaultEntry.objects.filter(user=self.user, last_accessed__lt=cutoff).delete()
