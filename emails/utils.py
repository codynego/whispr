# email_importance.py
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Initialize the model once
model = SentenceTransformer('all-MiniLM-L6-v2')

# Example important keywords
IMPORTANT_KEYWORDS = [
    "urgent", "action required", "meeting", "deadline", "CEO", "important", 
    "follow up", "please review", "immediate attention"
]

# Example important email snippets
IMPORTANT_EXAMPLES = [
    "Please respond immediately",
    "Action required for your account",
    "Meeting invite from CEO",
    "Project deadline approaching",
    "Critical update",
    "Please review this document",
    "Follow up required",
    "credit alert",
    "transaction successful",
]

# Precompute embeddings for examples
important_example_embeddings = model.encode(IMPORTANT_EXAMPLES)

def is_email_important(
    email_text: str, 
    keyword_weight: float = 0.4, 
    semantic_weight: float = 0.6, 
    similarity_threshold: float = 0.7
):
    """
    Determines if an email is important based on keywords and semantic similarity.

    Returns:
        tuple: (email_embedding: np.ndarray, is_important: bool, combined_score: float)
    """
    if not email_text or not email_text.strip():
        return None, False, 0.0

    email_text_lower = email_text.lower()

    # 1️⃣ Keyword score
    keyword_score = any(kw.lower() in email_text_lower for kw in IMPORTANT_KEYWORDS)
    keyword_score = 1.0 if keyword_score else 0.0

    # 2️⃣ Semantic similarity score
    email_embedding = model.encode([email_text])
    similarities = cosine_similarity(email_embedding, important_example_embeddings)
    semantic_score = float(np.max(similarities))

    # 3️⃣ Weighted combination
    combined_score = keyword_weight * keyword_score + semantic_weight * semantic_score
    is_important = combined_score >= similarity_threshold

    return email_embedding, is_important, combined_score




