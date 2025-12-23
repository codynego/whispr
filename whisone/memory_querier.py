from typing import List, Dict, Any, Optional
from django.utils import timezone
from .models import Memory
import openai
import numpy as np
from django.conf import settings


class MemoryQueryManager:
    """
    Hybrid memory query manager.
    Combines structured filters + semantic similarity.
    Can leverage task_plan to extract memory_types and emotions for smarter queries.
    """

    SEMANTIC_THRESHOLD = 0.75

    def __init__(self, user):
        self.user = user
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    # -------------------------
    # Main query method
    # -------------------------
    def query(
        self,
        keyword: Optional[str] = None,
        memory_types: Optional[List[str]] = None,
        emotions: Optional[List[str]] = None,
        min_importance: Optional[float] = None,
        time_after=None,
        time_before=None,
        task_plan: Optional[List[Dict[str, Any]]] = None,
        limit: int = 5,
        use_semantic: bool = True,
    ) -> List[Dict[str, Any]]:

        # --- Extract memory_types and emotions from task_plan ---
        if task_plan:
            plan_types = {t.get("params", {}).get("memory_type") for t in task_plan if t.get("params", {}).get("memory_type")}
            plan_emotions = {t.get("params", {}).get("emotion") for t in task_plan if t.get("params", {}).get("emotion")}
            if plan_types:
                memory_types = list(set(memory_types or []) | plan_types)
            if plan_emotions:
                emotions = list(set(emotions or []) | plan_emotions)

        memories = Memory.objects.filter(user=self.user)

        # -------------------------
        # 1. Structured filters
        # -------------------------
        if memory_types:
            memories = memories.filter(memory_type__in=memory_types)

        if emotions:
            memories = memories.filter(emotion__in=emotions)

        if min_importance is not None:
            memories = memories.filter(importance__gte=min_importance)

        if time_after:
            memories = memories.filter(created_at__gte=time_after)

        if time_before:
            memories = memories.filter(created_at__lte=time_before)

        memories = list(memories)

        # -------------------------
        # 2. Semantic search
        # -------------------------
        if keyword and use_semantic and memories:
            try:
                emb = self.client.embeddings.create(
                    model="text-embedding-3-small",
                    input=keyword,
                )
                query_embedding = emb.data[0].embedding
            except Exception:
                query_embedding = None

            if query_embedding:
                scored = []
                for mem in memories:
                    if not mem.embedding:
                        continue
                    sim = self._cosine(query_embedding, mem.embedding)
                    if sim >= self.SEMANTIC_THRESHOLD:
                        scored.append((sim, mem))

                # Sort by similarity + importance
                scored.sort(key=lambda x: (x[0], x[1].importance), reverse=True)
                memories = [m for _, m in scored[:limit]]
            else:
                memories = memories[:limit]
        else:
            memories = memories[:limit]

        # -------------------------
        # 3. Build results
        # -------------------------
        now = timezone.now()
        results = []

        for mem in memories:
            mem.updated_at = now
            mem.save(update_fields=["updated_at"])

            results.append({
                "memory_id": str(mem.id),
                "summary": mem.summary,
                "raw_text": mem.raw_text,
                "memory_type": mem.memory_type,
                "emotion": mem.emotion,
                "sentiment": mem.sentiment,
                "importance": mem.importance,
                "context": mem.context,
                "created_at": mem.created_at.isoformat(),
                "updated_at": mem.updated_at.isoformat(),
            })

        return results

    # -------------------------
    # Utils
    # -------------------------
    @staticmethod
    def _cosine(a, b) -> float:
        a, b = np.array(a), np.array(b)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
