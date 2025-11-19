from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q
from .models import KnowledgeVaultEntry
import hashlib

User = None  # Will be replaced with settings.AUTH_USER_MODEL in real usage


class KnowledgeVaultManager:
    """
    Knowledge Vault Manager for structured entries:
    - Ingest user memories (facts, events, tasks, goals, preferences, etc.)
    - Update memories intelligently
    - Query by keyword, entities, or relationships
    - Prune old memories
    """

    def __init__(self, user: User):
        self.user = user

    # ---------------------------
    # 1️⃣ Ingest Memory
    # ---------------------------
    def ingest_memory(
        self,
        content: str,
        entities: Dict[str, Any],
        relationships: List[Dict[str, str]],
        summary: str
    ) -> KnowledgeVaultEntry:
        """
        Add a new memory or update existing memory if same memory_id exists.
        """
        memory_id = self._generate_id(content)

        entry, created = KnowledgeVaultEntry.objects.update_or_create(
            user=self.user,
            memory_id=memory_id,
            defaults={
                "entities": entities,
                "relationships": relationships,
                "summary": summary,
                "timestamp": timezone.now(),
            }
        )

        return entry

    # ---------------------------
    # 2️⃣ Update Existing Memory
    # ---------------------------
    def update_memory(
        self,
        memory_id: str,
        entities: Optional[Dict[str, Any]] = None,
        relationships: Optional[List[Dict[str, str]]] = None,
        summary: Optional[str] = None,
    ) -> Optional[KnowledgeVaultEntry]:
        """
        Update an existing memory intelligently. Only updates provided fields.
        Merges entities and relationships instead of overwriting completely.
        """
        try:
            entry = KnowledgeVaultEntry.objects.get(user=self.user, memory_id=memory_id)
            updated = False

            # Merge entities
            if entities:
                for key, value in entities.items():
                    if key in entry.entities and isinstance(entry.entities[key], list):
                        entry.entities[key].extend(value)
                        # Deduplicate
                        entry.entities[key] = list({json.dumps(e, sort_keys=True) for e in entry.entities[key]})
                        entry.entities[key] = [json.loads(e) for e in entry.entities[key]]
                    else:
                        entry.entities[key] = value
                updated = True

            # Merge relationships
            if relationships:
                entry.relationships.extend(relationships)
                # Deduplicate
                entry.relationships = list({json.dumps(r, sort_keys=True) for r in entry.relationships})
                entry.relationships = [json.loads(r) for r in entry.relationships]
                updated = True

            if summary:
                entry.summary = summary
                updated = True

            if updated:
                entry.last_accessed = timezone.now()
                entry.save()

            return entry

        except KnowledgeVaultEntry.DoesNotExist:
            return None

    # ---------------------------
    # 3️⃣ Query Memories
    # ---------------------------
    def query(
        self,
        keyword: Optional[str] = None,
        entities: Optional[List[str]] = None,
        relationships: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5
    ) -> List[KnowledgeVaultEntry]:
        """
        Smart universal query engine for the Knowledge Vault.
        Supports:
        - keyword search
        - entity matching
        - relationship matching
        - custom filters passed by TaskPlanner/Executor
        """
        q = Q(user=self.user)

        # Standard keyword search
        if keyword:
            q &= Q(summary__icontains=keyword)

        # Entity search
        if entities:
            for e in entities:
                q &= Q(entities__icontains=e)

        # Relationship search
        if relationships:
            for r in relationships:
                q &= Q(relationships__icontains=r)

        if filters:
            for f in filters:
                if isinstance(f, dict) and "key" in f and "value" in f and f["value"] is not None:
                    q &= Q(**{f"{f['key']}__icontains": f["value"]})


        entries = KnowledgeVaultEntry.objects.filter(q).order_by("-timestamp")[:limit]

        # Update access timestamp
        for entry in entries:
            entry.last_accessed = timezone.now()
            entry.save(update_fields=["last_accessed"])

        return list(entries)


    # ---------------------------
    # 4️⃣ Fetch Recent Memories
    # ---------------------------
    def recent_memories(self, limit: int = 5) -> List[KnowledgeVaultEntry]:
        """
        Fetch the most recent memories.
        """
        entries = KnowledgeVaultEntry.objects.filter(user=self.user).order_by("-timestamp")[:limit]

        for entry in entries:
            entry.last_accessed = timezone.now()
            entry.save(update_fields=["last_accessed"])

        return list(entries)

    # ---------------------------
    # 5️⃣ Prune Old Memories
    # ---------------------------
    def prune_old_memory(self, days: int = 90):
        """
        Delete memories not accessed in the last `days`.
        """
        cutoff = timezone.now() - timezone.timedelta(days=days)
        KnowledgeVaultEntry.objects.filter(user=self.user, last_accessed__lt=cutoff).delete()

    # ---------------------------
    # 6️⃣ Utility: Generate Memory ID
    # ---------------------------
    def _generate_id(self, content: str) -> str:
        return hashlib.md5(content.encode("utf-8")).hexdigest()
