from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


model = SentenceTransformer("all-MiniLM-L6-v2")

# === Importance reference data ===
IMPORTANT_KEYWORDS = [
    "urgent", "action required", "meeting", "deadline", "CEO", "important",
    "follow up", "please review", "immediate attention", "project", "money",
    "credit alert", "transaction successful"
]

IMPORTANT_EXAMPLES = [
    "Please respond immediately",
    "Action required for your account",
    "Meeting invite from CEO",
    "Project deadline approaching",
    "Critical update",
    "Please review this document",
    "Follow up required",
    "Payment received",
]

important_example_embeddings = model.encode(IMPORTANT_EXAMPLES)


# === Importance Analyzer ===
def is_message_important(
    text: str,
    keyword_weight: float = 0.4,
    semantic_weight: float = 0.6,
    threshold: float = 0.7,
):
    """Return (embedding, is_important, score)"""
    if not text or not text.strip():
        return None, False, 0.0

    text_lower = text.lower()

    keyword_score = 1.0 if any(kw in text_lower for kw in IMPORTANT_KEYWORDS) else 0.0
    embedding = model.encode([text])
    semantic_score = float(np.max(cosine_similarity(embedding, important_example_embeddings)))

    combined = keyword_weight * keyword_score + semantic_weight * semantic_score
    return embedding, combined >= threshold, combined