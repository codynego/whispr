from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Optional, Tuple
from django.core.cache import cache
from hashlib import md5
import time  # For optional timing

# Global refs (preload in worker init if possible)
model = SentenceTransformer("all-MiniLM-L6-v2")
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


def is_message_important(
    text: str,
    user_rules: Optional[List['UserRule']] = None,
    sender_email: Optional[str] = None,  # New: Enable sender rules
    keyword_weight: float = 0.4,
    semantic_weight: float = 0.6,
    threshold: float = 0.7,
    compute_embedding: bool = True,  # New: Skip for rules-only (speedup)
) -> Tuple[Optional[np.ndarray], bool, float]:
    """Return (embedding, is_important, score)
    
    Analyzes message importance using semantic similarity and keywords.
    Overrides with user rules if provided and matching. Caches results.
    """
    if not text or not text.strip():
        return None, False, 0.0

    text_lower = text.lower().strip()
    
    # Cache: Hash text + rules + sender (fast lookup)
    cache_key = f"msg_imp:{md5(text_lower.encode()).hexdigest()[:12]}"
    if user_rules:
        rules_hash = md5(str([(r.id, r.value) for r in user_rules]).encode()).hexdigest()[:8]
        cache_key += f":{rules_hash}"
    if sender_email:
        cache_key += f":{md5(sender_email.lower().encode()).hexdigest()[:8]}"
    
    cached = cache.get(cache_key)
    if cached:
        return cached  # (embedding, is_important, score)

    # Rules override (enhanced with sender)
    rule_score = None
    if user_rules:
        max_importance = "low"
        for rule in [r for r in user_rules if r.is_active]:
            if rule.channel and rule.channel != "all":
                continue  # Caller should filter; or add channel param
            
            match = False
            if rule.rule_type in ["keyword", "body", "subject"]:
                if rule.value and rule.value.lower() in text_lower:
                    match = True
            elif rule.rule_type == "sender":
                if sender_email and rule.value and rule.value.lower() in sender_email.lower():
                    match = True
            elif rule.rule_type in ["attachment", "reply"]:
                # Stubs: Pass metadata/flag from caller if needed
                continue
            elif rule.rule_type == "ai":
                if rule.value and rule.value.lower() in text_lower:
                    match = True
            
            if match:
                if rule.importance == "critical":
                    max_importance = "critical"
                elif rule.importance == "high" and max_importance != "critical":
                    max_importance = "high"
                elif rule.importance == "medium" and max_importance != "high":
                    max_importance = "medium"
        
        importance_map = {"low": 0.2, "medium": 0.55, "high": 0.75, "critical": 0.95}
        rule_score = importance_map.get(max_importance, 0.5)
        if rule_score:  # Rules hit: Skip embedding if not forced
            embedding = None
            combined = rule_score
            semantic_score = 0.0  # Or approximate from rules
        else:
            embedding = None  # Defer

    # Fallback: Semantic + fuzzy keywords
    if embedding is None and compute_embedding:
        encode_start = time.perf_counter()  # Optional timing
        try:
            embedding = model.encode([text])
            print(f"DEBUG: Encoded in {time.perf_counter() - encode_start:.3f}s")  # Log for tuning
        except Exception as e:
            print(f"⚠️ Encoding failed: {e}")
            embedding = None

    if embedding is not None:
        # Fuzzy keywords: Score by match density (0-1)
        kw_matches = sum(1 for kw in IMPORTANT_KEYWORDS if kw in text_lower)
        keyword_score = min(kw_matches / max(len(IMPORTANT_KEYWORDS) * 0.3, 1), 1.0)  # ~30% matches = full score
        
        semantic_score = float(np.max(cosine_similarity(embedding, important_example_embeddings)))
        combined = keyword_weight * keyword_score + semantic_weight * semantic_score
    else:
        # No embedding: Keyword-only fallback
        keyword_score = 1.0 if any(kw in text_lower for kw in IMPORTANT_KEYWORDS) else 0.0
        combined = keyword_weight * keyword_score  # Or rule_score if set

    is_important = combined >= threshold

    # Cache (300s TTL)
    cache.set(cache_key, (embedding, is_important, combined), 300)
    return embedding, is_important, combined