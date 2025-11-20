from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np
import dateparser
from openai import OpenAI

class NaturalResolver:
    """
    Resolves natural language queries to a specific user object
    (Note, Reminder, Todo, Event) using keyword, date, entity, and semantic matching.
    Events are fetched via GoogleCalendarService instead of a local model.
    """

    def __init__(self, user, api_key: str, calendar_service=None, generate_event_embeddings=True):
        self.user = user
        self.client = OpenAI(api_key=api_key)
        self.calendar_service = calendar_service
        self.generate_event_embeddings = generate_event_embeddings

    # -------------------------
    # Public API
    # -------------------------
    def resolve(self, item_type: str, natural_query: str) -> Optional[dict]:
        items = self._get_items(item_type)

        # Precompute embeddings for items if missing
        for item in items:
            if not getattr(item, "embedding", None) and self.generate_event_embeddings:
                text = self._extract_text(item)
                try:
                    item.embedding = self._embed(text)
                except Exception:
                    item.embedding = None

        # 1. Keyword filter
        keyword_candidates = self._keyword_filter(items, natural_query)
        if len(keyword_candidates) == 1:
            return self._pack(keyword_candidates[0], confidence=0.90)

        # 2. Date/time filter
        date_candidates = self._date_filter(items, natural_query)
        if len(date_candidates) == 1:
            return self._pack(date_candidates[0], confidence=0.92)

        # 3. Entity filter
        entity_candidates = self._entity_filter(items, natural_query)
        if len(entity_candidates) == 1:
            return self._pack(entity_candidates[0], confidence=0.93)

        # 4. Semantic matching or fallback to text match
        candidates = keyword_candidates or date_candidates or entity_candidates or items
        result = self._semantic_match(candidates, natural_query)
        if result:
            return result

        # Fallback: simple substring match if semantic fails
        if not result:
            for item in candidates:
                text = self._extract_text(item).lower()
                if natural_query.lower() in text:
                    return self._pack(item, confidence=0.5)
        return None

    # -------------------------
    # Fetch items by type
    # -------------------------
    def _get_items(self, item_type: str) -> List:
        from whisone.models import Reminder, Note, Todo

        if item_type.lower() == "reminder":
            return list(Reminder.objects.filter(user=self.user))
        if item_type.lower() == "note":
            return list(Note.objects.filter(user=self.user))
        if item_type.lower() == "todo":
            return list(Todo.objects.filter(user=self.user))
        if item_type.lower() == "event":
            return self._fetch_calendar_events()
        return []

    def _fetch_calendar_events(self) -> List:
        if not self.calendar_service:
            return []

        events = self.calendar_service.get_events_for_today(max_results=50)
        class EventWrapper:
            def __init__(self, event):
                self.id = event.get("id")
                self.summary = event.get("summary") or ""
                start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
                if start:
                    try:
                        self.start_time = datetime.fromisoformat(start)
                    except Exception:
                        self.start_time = None
                else:
                    self.start_time = None
                self.embedding = None
        return [EventWrapper(e) for e in events]

    # -------------------------
    # Filters
    # -------------------------
    def _keyword_filter(self, items: List, query: str) -> List:
        words = [w.strip() for w in query.lower().split() if len(w) > 2]
        results = []
        for item in items:
            text = self._extract_text(item).lower()
            score = sum(1 for w in words if w in text)
            if score > 0:
                results.append(item)
        return results

    def _date_filter(self, items: List, query: str) -> List:
        dt = dateparser.parse(query)
        if not dt:
            return []

        candidates = []
        for item in items:
            item_dt = getattr(item, "remind_at", None) \
                    or getattr(item, "due", None) \
                    or getattr(item, "start_time", None)
            if item_dt and abs((item_dt - dt).total_seconds()) < 3600*12:  # 12-hour tolerance
                candidates.append(item)
        return candidates

    def _entity_filter(self, items: List, query: str) -> List:
        q_lower = query.lower()
        candidates = []
        for item in items:
            entities = getattr(item, "entities", {}) or {}
            for ent_list in entities.values():
                if any(ent.lower() in q_lower for ent in ent_list):
                    candidates.append(item)
        return candidates

    # -------------------------
    # Semantic matching
    # -------------------------
    def _semantic_match(self, items: List, query: str) -> Optional[dict]:
        if not items:
            return None

        query_emb = self._embed(query)
        ranked = []
        for item in items:
            item_emb = getattr(item, "embedding", None)
            if item_emb is None:
                continue
            sim = self._cosine(query_emb, item_emb)
            ranked.append((sim, item))

        if not ranked:
            return None

        ranked.sort(key=lambda x: x[0], reverse=True)
        best_sim, best_item = ranked[0]
        if best_sim < 0.3:
            return None
        return self._pack(best_item, confidence=best_sim)

    # -------------------------
    # Helpers
    # -------------------------
    def _embed(self, text: str) -> List[float]:
        resp = self.client.embeddings.create(model="text-embedding-3-small", input=text)
        return resp.data[0].embedding

    def _extract_text(self, item) -> str:
        for field in ["text", "content", "task", "title", "summary"]:
            if hasattr(item, field):
                return getattr(item, field) or ""
        return ""

    def _cosine(self, a: List[float], b: List[float]) -> float:
        a = np.array(a)
        b = np.array(b)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def _pack(self, item, confidence: float) -> dict:
        return {
            "object_id": item.id,
            "matched_text": self._extract_text(item),
            "confidence": confidence
        }
