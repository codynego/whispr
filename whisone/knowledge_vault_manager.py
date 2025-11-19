from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q
from .models import KnowledgeVaultEntry
import hashlib
import uuid

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
        Add a new memory as a separate entry every time.
        """
        memory_id = str(uuid.uuid4())  # unique for each memory

        entry = KnowledgeVaultEntry.objects.create(
            user=self.user,
            memory_id=memory_id,
            entities=entities,
            relationships=relationships,
            summary=summary,
            timestamp=timezone.now()
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
        entities: Optional[List[str]] = None,  # List of entity types
        relationships: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: int = 5
    ) -> List[KnowledgeVaultEntry]:
        """
        Universal query engine for the Knowledge Vault.

        Args:
            keyword: Search term in summary or inside entity lists.
            entities: List of entity types to search keyword in (e.g., ["emotions", "tasks"]).
            relationships: List of relationship strings to match.
            filters: List of dicts with 'key' and 'value' for additional filters (e.g., after/before).
            limit: Maximum number of entries to return.

        Returns:
            List of KnowledgeVaultEntry objects.
        """
        q = Q(user=self.user)

        # Keyword search in summary
        if keyword:
            q &= Q(summary__icontains=keyword)

        # Keyword search inside entity lists
        if entities and keyword:
            entity_q = Q()
            for entity_type in entities:
                # Check if the keyword exists inside the JSONField list
                entity_q |= Q(**{f"entities__{entity_type}__contains": [keyword]})
            q &= entity_q

        # Relationship search
        if relationships:
            for r in relationships:
                q &= Q(relationships__icontains=r)

        # Custom filters (time ranges etc.)
        if filters:
            for f in filters:
                if isinstance(f, dict) and "key" in f and "value" in f:
                    key = f["key"]
                    value = f["value"]
                    if value is None:
                        continue
                    if key == "after":
                        q &= Q(timestamp__gte=value)
                    elif key == "before":
                        q &= Q(timestamp__lte=value)
                    elif key in ["entities", "relationships", "summary"]:
                        q &= Q(**{f"{key}__icontains": value})

        print("query", q)
        # Fetch entries
        entries = KnowledgeVaultEntry.objects.filter(q).order_by("-timestamp")[:limit]

        # Update last_accessed timestamp
        now = timezone.now()
        for entry in entries:
            entry.last_accessed = now
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
