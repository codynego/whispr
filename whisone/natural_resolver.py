from datetime import datetime
from typing import List, Optional, Dict, Any, Union
import numpy as np
import dateparser
from openai import OpenAI


class NaturalResolver:
    """
    Enhanced NaturalResolver that correctly resolves natural language queries
    to local Django objects (Note, Reminder, Todo) OR Google Calendar events.

    Returns consistent dict with:
        - object_id: int (Django PK) or str (Google Calendar event ID)
        - object_type: "django" | "gcal"
        - item_type: "note" | "reminder" | "todo" | "event"
    """

    def __init__(
        self,
        user,
        api_key: str,
        calendar_service=None,
        generate_event_embeddings: bool = True,
        embedding_model: str = "text-embedding-3-small",
    ):
        self.user = user
        self.client = OpenAI(api_key=api_key)
        self.calendar_service = calendar_service
        self.generate_event_embeddings = generate_event_embeddings
        self.embedding_model = embedding_model

        # Cache embeddings per session to avoid re-computing
        self._embedding_cache = {}

    def resolve(self, item_type: str, natural_query: str) -> Optional[Dict[str, Any]]:
        """
        Main entry point.
        Returns dict with resolved object or None.
        """
        if not natural_query or not natural_query.strip():
            return None

        query = natural_query.strip().lower()
        items = self._get_items(item_type.lower())

        if not items:
            return None

        # Pre-compute embeddings (with cache)
        for item in items:
            text = self._extract_text(item)
            if text and text not in self._embedding_cache:
                try:
                    self._embedding_cache[text] = self._embed(text)
                except Exception as e:
                    print(f"Embedding failed for text: {text[:50]}... | Error: {e}")
                    self._embedding_cache[text] = None
            item.embedding = self._embedding_cache.get(text)

        # Phase 1: Fast filters (exact-ish)
        candidates = self._keyword_filter(items, query)
        if len(candidates) == 1:
            return self._pack(candidates[0], confidence=0.95, source="keyword")

        candidates = self._date_filter(items, natural_query) or candidates
        if len(candidates) == 1:
            return self._pack(candidates[0], confidence=0.94, source="date")

        candidates = self._entity_filter(items, query) or candidates
        if len(candidates) == 1:
            return self._pack(candidates[0], confidence=0.93, source="entity")

        # Phase 2: Semantic search on candidates
        if candidates:
            semantic_result = self._semantic_match(candidates, natural_query)
            if semantic_result:
                return semantic_result

        # Phase 3: Fallback substring on original items
        for item in items:
            text = self._extract_text(item).lower()
            if query in text or any(word in text for word in query.split() if len(word) > 3):
                return self._pack(item, confidence=0.6, source="substring")

        return None

    # ===========================
    # Item Fetching
    # ===========================
    def _get_items(self, item_type: str) -> List[Any]:
        from whisone.models import Reminder, Note, Todo

        if item_type == "reminder":
            return list(Reminder.objects.filter(user=self.user).order_by("-remind_at"))
        if item_type == "note":
            return list(Note.objects.filter(user=self.user).order_by("-created_at"))
        if item_type == "todo":
            return list(Todo.objects.filter(user=self.user).order_by("-created_at"))
        if item_type == "event":
            return self._fetch_calendar_events()
        return []

    def _fetch_calendar_events(self) -> List[Any]:
        if not self.calendar_service:
            return []

        try:
            events = self.calendar_service.get_events_for_today(max_results=100)
        except Exception as e:
            print(f"Calendar fetch failed: {e}")
            return []

        class EventWrapper:
            def __init__(self, event_data: dict):
                self.gcal_id = event_data.get("id")  # Google Calendar string ID
                self.summary = (event_data.get("summary") or "No title").strip()
                self.description = (event_data.get("description") or "").strip()
                start = event_data.get("start", {}).get("dateTime") or event_data.get("start", {}).get("date")
                self.start_time = self._parse_datetime(start) if start else None
                self.embedding = None
                self.item_type = "event"

            def _parse_datetime(self, dt_str: str):
                try:
                    if "T" in dt_str:
                        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    return datetime.fromisoformat(dt_str)
                except:
                    return dateparser.parse(dt_str)

        return [EventWrapper(e) for e in events if e.get("status") != "cancelled"]

    # ===========================
    # Filters
    # ===========================
    def _keyword_filter(self, items: List[Any], query: str) -> List[Any]:
        words = [w for w in query.lower().split() if len(w) > 2]
        if not words:
            return items

        def score_item(item):
            text = self._extract_text(item).lower()
            return sum(2 if w in text else 0 for w in words) + sum(1 for w in words if w in text.split())

        scored = [(score_item(i), i) for i in items]
        scored = [item for score, item in scored if score > 0]
        return scored[:15]  # limit for performance

    def _date_filter(self, items: List[Any], query: str) -> List[Any]:
        parsed = dateparser.parse(query, settings={'PREFER_DATES_FROM': 'future'})
        if not parsed:
            return []

        tolerance = timedelta(hours=24)
        matches = []
        for item in items:
            dt = getattr(item, "remind_at", None) or getattr(item, "due", None) or getattr(item, "start_time", None)
            if dt and abs(dt - parsed) <= tolerance:
                matches.append(item)
        return matches

    def _entity_filter(self, items: List[Any], query: str) -> List[Any]:
        entities_in_query = {w for w in query.lower().split() if len(w) > 3}
        matches = []
        for item in items:
            entities = getattr(item, "entities", {}) or {}
            flat_entities = {e.lower() for ent_list in entities.values() for e in ent_list}
            if entities_in_query.intersection(flat_entities):
                matches.append(item)
        return matches

    # ===========================
    # Semantic Matching
    # ===========================
    def _semantic_match(self, items: List[Any], query: str) -> Optional[Dict]:
        if not items:
            return None

        try:
            query_emb = self._embed(query)
        except Exception:
            return None

        scores = []
        for item in items:
            if not hasattr(item, "embedding") or item.embedding is None:
                continue
            sim = self._cosine(query_emb, item.embedding)
            if sim > 0.65:  # strong match
                scores.append((sim, item))

        if not scores:
            return None

        scores.sort(key=lambda x: x[0], reverse=True)
        best_sim, best_item = scores[0]
        return self._pack(best_item, confidence=round(best_sim, 3), source="semantic")

    # ===========================
    # Helpers
    # ===========================
    def _embed(self, text: str) -> List[float]:
        if not text.strip():
            return [0.0] * 1536
        resp = self.client.embeddings.create(
            model=self.embedding_model,
            input=text[:8000]  # avoid token limit
        )
        return resp.data[0].embedding

    def _extract_text(self, item) -> str:
        if hasattr(item, "summary"):  # EventWrapper
            desc = item.description or ""
            return f"{item.summary} {desc}".strip()
        if hasattr(item, "text"):
            return item.text or ""
        if hasattr(item, "content"):
            return item.content or ""
        if hasattr(item, "task"):
            return item.task or ""
        if hasattr(item, "title"):
            return item.title or ""
        return ""

    def _cosine(self, a: List[float], b: List[float]) -> float:
        a_np = np.array(a)
        b_np = np.array(b)
        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a_np, b_np) / (norm_a * norm_b))

    def _pack(self, item, confidence: float, source: str = "unknown") -> Dict[str, Any]:
        if hasattr(item, "gcal_id"):  # Google Calendar event
            return {
                "object_id": item.gcal_id,
                "object_type": "gcal",
                "item_type": "event",
                "matched_text": self._extract_text(item),
                "confidence": confidence,
                "source": source,
            }
        else:  # Django model instance
            return {
                "object_id": item.pk or item.id,
                "object_type": "django",
                "item_type": getattr(item, "item_type", type(item).__name__.lower()),
                "matched_text": self._extract_text(item),
                "confidence": confidence,
                "source": source,
            }