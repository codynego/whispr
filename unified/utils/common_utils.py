from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Optional, Tuple
from django.db import models
from django.conf import settings
from celery import shared_task


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
@shared_task
def is_message_important(
    text: str,
    user_rules: Optional[List['UserRule']] = None,
    keyword_weight: float = 0.4,
    semantic_weight: float = 0.6,
    threshold: float = 0.7,
) -> Tuple[Optional[np.ndarray], bool, float]:
    """Return (embedding, is_important, score)
    
    Analyzes message importance using semantic similarity and keywords.
    Overrides with user rules if provided and matching.
    """
    if not text or not text.strip():
        return None, False, 0.0

    text_lower = text.lower()

    # Check user rules first for override
    rule_score = None
    if user_rules:
        max_importance = "low"
        for rule in [r for r in user_rules if r.is_active]:
            if rule.channel and rule.channel != "all":  # Skip if channel-specific and not matching (assume 'all' or None for general)
                continue
            
            match = False
            if rule.rule_type in ["keyword", "body", "subject"]:
                # For text-based rules, check if value is in text
                if rule.value and rule.value.lower() in text_lower:
                    match = True
            elif rule.rule_type == "attachment":
                # Would need metadata; skip for text-only
                continue
            elif rule.rule_type == "reply":
                # Would need metadata; skip
                continue
            elif rule.rule_type == "sender":
                # Would need sender; skip
                continue
            elif rule.rule_type == "ai":
                # Could add semantic check, but for now skip or treat as keyword
                if rule.value and rule.value.lower() in text_lower:
                    match = True
            
            if match:
                if rule.importance == "critical":
                    max_importance = "critical"
                elif rule.importance == "high" and max_importance != "critical":
                    max_importance = "high"
                elif rule.importance == "medium" and max_importance in ["low", "medium"]:
                    max_importance = "medium"
                # low doesn't downgrade
        
        # Map to score
        importance_map = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}
        rule_score = importance_map.get(max_importance, 0.5)

    # If no rule match, fall back to semantic/keyword calculation
    if rule_score is None:
        keyword_score = 1.0 if any(kw in text_lower for kw in IMPORTANT_KEYWORDS) else 0.0
        embedding = model.encode([text])
        semantic_score = float(np.max(cosine_similarity(embedding, important_example_embeddings)))

        combined = keyword_weight * keyword_score + semantic_weight * semantic_score
    else:
        # Still compute embedding for consistency
        embedding = model.encode([text])
        combined = rule_score

    is_important = combined >= threshold
    return embedding, is_important, combined

