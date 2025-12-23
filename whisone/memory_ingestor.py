from typing import Dict, Any, Optional, List
from django.db import transaction
from django.utils import timezone
from .models import Memory
import openai
from django.conf import settings
import numpy as np


class MemoryIngestor:
    """
    Saves structured Memory objects.
    Supports ingestion of single memory or list of memories (e.g., tasks).
    """

    DUPLICATE_SIM_THRESHOLD = 0.88

    def __init__(self, user):
        self.user = user
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    # ------------------------
    # Public ingestion method
    # ------------------------
    def ingest(
        self,
        memory_data: Dict[str, Any] | List[Dict[str, Any]],
        allow_merge: bool = True,
    ) -> List[Memory]:
        """
        Ingest a single memory dict or a list of memory dicts.
        Returns list of Memory objects created or updated.
        """
        if isinstance(memory_data, dict):
            memory_data = [memory_data]

        stored_memories = []

        for mem in memory_data:
            embedding = self._embed(mem["raw_text"])

            with transaction.atomic():
                if allow_merge:
                    existing = self._find_similar_memory(embedding)
                    if existing:
                        stored_memories.append(self._merge(existing, mem, embedding))
                        continue

                memory = Memory.objects.create(
                    user=self.user,
                    raw_text=mem["raw_text"],
                    summary=mem["summary"],
                    memory_type=mem["memory_type"],
                    emotion=mem.get("emotion"),
                    sentiment=mem.get("sentiment"),
                    importance=mem.get("importance", 0.5),
                    context=mem.get("context", {}),
                    embedding=embedding,
                )
                stored_memories.append(memory)

        return stored_memories

    # ------------------------
    # Helpers
    # ------------------------
    def _embed(self, text: str):
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def _find_similar_memory(self, embedding) -> Optional[Memory]:
        memories = Memory.objects.filter(user=self.user).exclude(embedding=None)

        for mem in memories:
            sim = self._cosine_similarity(mem.embedding, embedding)
            if sim >= self.DUPLICATE_SIM_THRESHOLD:
                return mem

        return None

    def _merge(
        self,
        memory: Memory,
        new_data: Dict[str, Any],
        embedding,
    ) -> Memory:
        memory.summary = new_data["summary"]
        memory.emotion = new_data.get("emotion") or memory.emotion
        memory.sentiment = new_data.get("sentiment") or memory.sentiment
        memory.importance = max(memory.importance, new_data.get("importance", 0.5))
        memory.context.update(new_data.get("context", {}))
        memory.embedding = embedding
        memory.updated_at = timezone.now()
        memory.save()
        return memory

    @staticmethod
    def _cosine_similarity(a, b) -> float:
        a, b = np.array(a), np.array(b)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
