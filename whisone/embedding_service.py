import openai
import numpy as np
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Handles creating embeddings using OpenAI models.
    Uses caching + batching where possible.
    """
    MODEL = "text-embedding-3-large"  # best universal option

    def __init__(self, api_key=None):
        openai.api_key = api_key or settings.OPENAI_API_KEY

    def embed(self, text: str):
        """
        Returns a list of floats (embedding vector).
        """
        if not text:
            return None

        try:
            resp = openai.embeddings.create(
                model=self.MODEL,
                input=text,
            )
            return resp.data[0].embedding
        except Exception as e:
            logger.exception("Embedding error: %s", e)
            return None

    @staticmethod
    def cosine_sim(a, b):
        """
        Compute cosine similarity between two vectors.
        """
        if not a or not b:
            return 0.0
        a = np.array(a)
        b = np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
