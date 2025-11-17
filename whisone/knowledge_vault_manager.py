from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Q
from .models import KnowledgeVaultEntry, UserPreference
import hashlib
import json
from django.conf import settings
from .embedding_service import EmbeddingService

User = settings.AUTH_USER_MODEL

class KnowledgeVaultManager:
    """
    Production-ready Knowledge Vault Manager:
    - Ingest memory from user interactions or external sources.
    - Update knowledge vault entries intelligently.
    - Maintain aggregated user preferences.
    - Query for context or important information.
    """

    def __init__(self, user: User):
        self.user = user
        # Ensure preference model exists
        self.pref_model, _ = UserPreference.objects.get_or_create(user=user)
        self.embedding_service = EmbeddingService()

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        """
        if not vec1 or not vec2:
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(a * a for a in vec2) ** 0.5
        return dot / (norm1 * norm2) if norm1 * norm2 != 0 else 0.0

    # ---------------------------
    # 1️⃣ Ingest Memory
    # ---------------------------
    def ingest_memory(self, content: str, entities: List[str], summary: str, prefs: Optional[Dict[str, Any]] = None) -> KnowledgeVaultEntry:
        """
        Add new memory to the vault or update existing one if similar content exists.
        """
        memory_id = hashlib.md5(content.encode("utf-8")).hexdigest()
        embedding = self.embedding_service.embed(summary)

        entry, created = KnowledgeVaultEntry.objects.update_or_create(
            user=self.user,
            memory_id=memory_id,
            defaults={
                "entities": entities,
                "summary": summary,
                "preferences": prefs or {},
                "embedding": embedding,
                "timestamp": timezone.now()
            }
        )
        # Update aggregated preferences
        self.update_preferences(prefs or {})
        return entry

    # ---------------------------
    # 2️⃣ Update Preferences
    # ---------------------------
    def update_preferences(self, new_prefs: Dict[str, Any]):
        """
        Merge new preferences with existing preference model intelligently.
        """
        if not new_prefs:
            return

        updated_prefs = self.pref_model.preferences.copy()
        for k, v in new_prefs.items():
            # Simple merge: overwrite, or implement more complex logic here
            updated_prefs[k] = v

        self.pref_model.preferences = updated_prefs
        self.pref_model.save()

    # ---------------------------
    # 3️⃣ Query Knowledge
    # ---------------------------
    def query(self, keyword: str, entities: Optional[List[str]] = None, limit: int = 5) -> List[KnowledgeVaultEntry]:
        """
        Search for relevant memories by keyword and/or entities, ranked by embedding similarity if keyword provided.
        Falls back to timestamp ordering if no keyword.
        """
        # Build initial filter query
        q = Q(summary__icontains=keyword) | Q(entities__icontains=keyword)
        if entities:
            for e in entities:
                q |= Q(entities__icontains=e)
        print("Querying Knowledge Vault with:", q)

        entries = KnowledgeVaultEntry.objects.filter(user=self.user).filter(q)

        # If keyword provided, rank by similarity
        if keyword.strip():
            query_embedding = self.embedding_service.embed(keyword)
            scored_entries = []
            for entry in entries:
                similarity = self._cosine_similarity(query_embedding, entry.embedding)
                scored_entries.append((similarity, entry))
            # Sort by similarity descending
            scored_entries.sort(key=lambda x: x[0], reverse=True)
            result = [entry for _, entry in scored_entries[:limit]]
        else:
            # Fallback to timestamp ordering
            result = list(entries.order_by("-timestamp")[:limit])

        # Update last_accessed for returned entries (assuming model has this field)
        for entry in result:
            entry.last_accessed = timezone.now()
            entry.save(update_fields=["last_accessed"])

        return result

    # ---------------------------
    # 4️⃣ Delete / Prune Memory
    # ---------------------------
    def prune_old_memory(self, days: int = 90):
        """
        Delete entries that haven't been accessed in the last `days`.
        """
        cutoff = timezone.now() - timezone.timedelta(days=days)
        KnowledgeVaultEntry.objects.filter(user=self.user, last_accessed__lt=cutoff).delete()

    # ---------------------------
    # 5️⃣ Update Existing Entry
    # ---------------------------
    def update_memory(self, memory_id: str, summary: Optional[str] = None, entities: Optional[List[str]] = None, prefs: Optional[Dict[str, Any]] = None) -> Optional[KnowledgeVaultEntry]:
        """
        Update an existing memory intelligently. Only updates fields provided.
        Re-embeds if summary changes.
        """
        try:
            entry = KnowledgeVaultEntry.objects.get(user=self.user, memory_id=memory_id)
            updated = False
            if summary is not None:
                entry.summary = summary
                entry.embedding = self.embedding_service.embed(summary)
                updated = True
            if entities is not None:
                entry.entities = entities
                updated = True
            if prefs:
                entry.preferences.update(prefs)
                self.update_preferences(prefs)
                updated = True
            if updated:
                entry.save()
            return entry
        except KnowledgeVaultEntry.DoesNotExist:
            return None

    # ---------------------------
    # 6️⃣ Fetch Most Recent Memories
    # ---------------------------
    def recent_memories(self, limit: int = 5) -> List[KnowledgeVaultEntry]:
        return KnowledgeVaultEntry.objects.filter(user=self.user).order_by("-timestamp")[:limit]
