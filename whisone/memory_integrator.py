import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from difflib import SequenceMatcher

from django.utils import timezone
from django.conf import settings
from django.db import transaction

# Import your existing components (adjust import paths to your project)
from .memory_extractor import MemoryExtractor
from .knowledge_vault_manager import KnowledgeVaultManager
from .models import KnowledgeVaultEntry  # ensure this exists in your app
from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def _similarity(a: str, b: str) -> float:
    """Simple normalized string similarity between two strings (0..1)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


class MemoryIntegrator:
    """
    Integrates extracted memory into the Knowledge Vault intelligently.

    Responsibilities:
      - Accept extracted memory (or raw content + run extractor internally)
      - Detect duplicates / near-duplicates and merge/update rather than blindly creating
      - Update aggregated user preferences
      - Trigger downstream actions (notifications, automation creation, gap detection)
      - Provide extension points (callbacks) so you can plug notification/automation systems

    Usage:
      integrator = MemoryIntegrator(user, extractor, vault_manager,
                                    notify_callback=my_notify_func,
                                    automation_callback=my_automation_func,
                                    gap_detector=my_gap_detector)
      integrator.ingest_from_source(content, source_type="email", timestamp=ts)
    """

    def __init__(
        self,
        user,
        extractor: Optional[MemoryExtractor] = None,
        vault_manager: Optional[KnowledgeVaultManager] = None,
        notify_callback: Optional[Callable[[dict], None]] = None,
        automation_callback: Optional[Callable[[dict], None]] = None,
        gap_detector: Optional[Callable[[KnowledgeVaultEntry], List[dict]]] = None,
        similarity_threshold: float = 0.75,
    ):
        self.user = user
        self.extractor = extractor or MemoryExtractor(openai_api_key=settings.OPENAI_API_KEY)
        self.vault = vault_manager or KnowledgeVaultManager(user)
        # Callbacks (optional) — expected to accept a dict payload
        self.notify = notify_callback
        self.automate = automation_callback
        # Gap detector should return list of suggested actions (or empty)
        self.gap_detector = gap_detector
        self.similarity_threshold = similarity_threshold

    # -------------------------
    # MAIN ENTRY
    # -------------------------
    @transaction.atomic
    def ingest_from_source(
        self,
        content: str,
        source_type: str,
        timestamp: Optional[datetime] = None,
        allow_trigger_actions: bool = True,
    ) -> KnowledgeVaultEntry:
        """
        Ingest raw content from a source (email, calendar event, user_message, note).
        Steps:
          1. Extract structured memory (entities, summary, preferences)
          2. Look for similar vault entries (by hash and fuzzy similarity)
          3. Create, update, or merge as appropriate
          4. Update aggregated preferences
          5. Run gap detection (optional) and trigger actions/notifications

        Returns the KnowledgeVaultEntry that represents the final stored memory.
        """
        timestamp = timestamp or timezone.now()
        logger.debug("MemoryIntegrator: extracting memory for user=%s source=%s", self.user, source_type)

        extracted = self.extractor.extract(content, source_type=source_type, timestamp=timestamp)
        # extracted keys: id, source_type, timestamp, entities, preferences, summary
        summary = extracted.get("summary", "") or ""
        entities = extracted.get("entities", []) or []
        prefs = extracted.get("preferences", {}) or {}
        memory_id = extracted.get("id")

        # 1. Try exact/fast match using memory_id (deterministic hash from extractor)
        existing = None
        if memory_id:
            try:
                existing = KnowledgeVaultEntry.objects.get(user=self.user, memory_id=memory_id)
                logger.debug("MemoryIntegrator: exact memory_id match found, updating entry=%s", memory_id)
            except KnowledgeVaultEntry.DoesNotExist:
                existing = None

        # 2. If no exact match, search for similar entries
        if not existing:
            existing = self._find_similar_entry(summary, entities)

        if existing:
            # 3a. If similar enough, merge/update
            logger.info("MemoryIntegrator: merging into existing entry id=%s", existing.memory_id)
            merged_entry = self._merge_entries(existing, summary, entities, prefs, timestamp)
            # 4. Update preferences
            self.vault.update_preferences(prefs or {})
            # 5. Run gap detection & actions
            if allow_trigger_actions:
                self._post_ingest_actions(merged_entry, content)
            return merged_entry
        else:
            # 3b. No existing -> create a new vault entry
            logger.info("MemoryIntegrator: creating new vault entry id=%s", memory_id)
            entry = self.vault.ingest_memory(content=summary, entities=entities, summary=summary, prefs=prefs)
            # Update preferences
            self.vault.update_preferences(prefs or {})
            if allow_trigger_actions:
                self._post_ingest_actions(entry, content)
            return entry

    # -------------------------
    # FIND SIMILAR ENTRY
    # -------------------------
    def _find_similar_entry(self, summary: str, entities: List[str]) -> Optional[KnowledgeVaultEntry]:
        """
        Finds the most similar KnowledgeVaultEntry using embeddings.
        Strategy:
        - generate embedding for incoming summary
        - fetch last N entries (N=200 by default)
        - compute cosine similarity against stored embeddings
        - if similarity >= threshold, return matched entry
        """

        candidates = self.vault.recent_memories(limit=200)
        if not candidates:
            return None

        incoming_embedding = self.vault.embedding_service.embed(summary)
        if incoming_embedding is None:
            return None

        best_entry = None
        best_score = 0.0

        for cand in candidates:
            if not cand.embedding:
                continue

            score = EmbeddingService.cosine_sim(incoming_embedding, cand.embedding)
            if score > best_score:
                best_score = score
                best_entry = cand

        if best_score >= self.similarity_threshold:  # e.g. 0.85 recommended
            logger.debug(f"[EmbeddingMatch] Best score={best_score}")
            return best_entry

        return None


    # -------------------------
    # MERGE ENTRIES
    # -------------------------
    def _merge_entries(
        self,
        entry: KnowledgeVaultEntry,
        new_summary: str,
        new_entities: List[str],
        new_prefs: Dict[str, Any],
        new_timestamp: datetime,
    ) -> KnowledgeVaultEntry:
        """
        Merge incoming memory with an existing entry:
          - Append summary if new useful info
          - Merge entities (unique)
          - Update timestamp and last_accessed
          - Update preferences for entry and call vault-level preference merge
        """
        changed = False
        # Merge summary: if new summary adds unique content, append it
        if new_summary and new_summary not in (entry.summary or ""):
            # small heuristic: only append if similarity below a higher threshold
            sim = _similarity(new_summary, entry.summary or "")
            if sim < 0.95:
                entry.summary = (entry.summary or "") + "\n\n" + new_summary
                changed = True

        # Merge entities (unique)
        old_entities = set([e for e in (entry.entities or [])])
        incoming_entities = set(new_entities or [])
        merged_entities = list(old_entities | incoming_entities)
        if set(merged_entities) != old_entities:
            entry.entities = merged_entities
            changed = True

        # Merge preferences specific to this entry
        if new_prefs:
            entry_prefs = entry.preferences or {}
            # overwrite with incoming, but you might implement more nuanced logic
            entry_prefs.update(new_prefs)
            entry.preferences = entry_prefs
            changed = True
            # Also update aggregated vault preferences
            self.vault.update_preferences(new_prefs)

        # Update timestamps
        entry.timestamp = new_timestamp or timezone.now()
        entry.last_accessed = timezone.now()
        if changed:
            entry.save()
            logger.debug("MemoryIntegrator: merged and saved entry id=%s", entry.memory_id)
        else:
            # still update access time
            entry.save(update_fields=["last_accessed"])
        return entry

    # -------------------------
    # POST-INGEST ACTIONS
    # -------------------------
    def _post_ingest_actions(self, entry: KnowledgeVaultEntry, raw_content: str):
        """
        After ingesting or merging an entry:
          - Run gap detection (either built-in heuristics or provided gap_detector)
          - Trigger user notifications, automations, or create tasks depending on results
        """
        # 1) Gap detection (customizable)
        suggested_actions = []
        if self.gap_detector:
            try:
                suggested_actions = self.gap_detector(entry)
            except Exception as e:
                logger.exception("MemoryIntegrator: gap_detector raised: %s", e)
        else:
            # Basic heuristic gap detection:
            suggested_actions = self._basic_gap_detector(entry)

        # 2) If suggestions exist, either notify user or run automations depending on user prefs
        if suggested_actions:
            payload = {
                "user_id": getattr(self.user, "id", None),
                "entry_id": entry.memory_id,
                "suggestions": suggested_actions,
                "summary": entry.summary,
            }
            logger.info("MemoryIntegrator: found %d gap suggestions", len(suggested_actions))
            # Notify
            if self.notify:
                try:
                    self.notify(payload)
                except Exception as e:
                    logger.exception("MemoryIntegrator.notify callback error: %s", e)
            # Optionally attempt automation
            if self.automate:
                try:
                    self.automate(payload)
                except Exception as e:
                    logger.exception("MemoryIntegrator.automate callback error: %s", e)

    # -------------------------
    # BASIC GAP DETECTION HEURISTIC
    # -------------------------
    def _basic_gap_detector(self, entry: KnowledgeVaultEntry) -> List[Dict[str, Any]]:
        """
        Very simple heuristic gap detector:
          - If text mentions 'deadline', 'due', 'interview', 'follow up', etc and there's no reminder present for this entity,
            recommend creating a reminder / follow-up.
        This is a fallback — replace with a better gap_detector using embeddings / rules.
        """
        text = (entry.summary or "").lower()
        keywords = ["deadline", "due", "interview", "follow up", "follow-up", "urgent", "action required", "respond", "reply"]
        found = [k for k in keywords if k in text]
        suggestions = []
        if found:
            suggestions.append({
                "action": "create_reminder",
                "reason": f"Detected keywords: {found} in memory; no follow-up found",
                "params": {
                    "title": f"Follow up: {entry.summary[:80]}",
                    "datetime_hint": None,
                    "service": "whatsapp"
                }
            })
        return suggestions

    # -------------------------
    # Reconcile Conflicts (optional)
    # -------------------------
    def reconcile_conflicts(self, entry: KnowledgeVaultEntry, authoritative_data: Dict[str, Any]) -> KnowledgeVaultEntry:
        """
        If you receive new authoritative data (e.g., user explicitly edits a saved preference or marks something 'resolved'),
        call this to reconcile and update the vault entry.
        """
        # Simple behavior: overwrite fields provided, and update timestamp
        if "summary" in authoritative_data:
            entry.summary = authoritative_data["summary"]
        if "entities" in authoritative_data:
            entry.entities = authoritative_data["entities"]
        if "preferences" in authoritative_data:
            p = entry.preferences or {}
            p.update(authoritative_data["preferences"])
            entry.preferences = p
            self.vault.update_preferences(authoritative_data["preferences"])
        entry.last_accessed = timezone.now()
        entry.save()
        return entry

    # -------------------------
    # OPTIONAL: prune/archive
    # -------------------------
    def prune_or_archive(self, days: int = 365):
        """
        Use the vault manager to prune or archive very old entries.
        """
        self.vault.prune_old_memory(days=days)
