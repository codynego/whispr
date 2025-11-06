# from sentence_transformers import SentenceTransformer
# from sklearn.metrics.pairwise import cosine_similarity
# import numpy as np
# from typing import List, Optional, Tuple
# from django.core.cache import cache
# import hashlib  # For md5 hashing
# import time  # For optional timing

# # Global model (lazy init)
# model = None  # Init here to avoid NameError in get_model

# def get_model():
#     global model
#     if model is None:
#         print("Loading SentenceTransformer model once per worker…")
#         model = SentenceTransformer("all-MiniLM-L6-v2")
#     return model

# # Load model and compute static embeddings at module import
# model = get_model()
# IMPORTANT_KEYWORDS = [
#     "urgent", "action required", "meeting", "deadline", "CEO", "important",
#     "follow up", "please review", "immediate attention", "project", "money",
#     "credit alert", "transaction successful"
# ]
# IMPORTANT_EXAMPLES = [
#     "Please respond immediately",
#     "Action required for your account",
#     "Meeting invite from CEO",
#     "Project deadline approaching",
#     "Critical update",
#     "Please review this document",
#     "Follow up required",
#     "Payment received",
# ]
# important_example_embeddings = model.encode(IMPORTANT_EXAMPLES)


# def is_message_important(
#     text: str,
#     user_rules: Optional[List['UserRule']] = None,
#     sender_email: Optional[str] = None,
#     keyword_weight: float = 0.4,
#     semantic_weight: float = 0.6,
#     threshold: float = 0.7,
#     compute_embedding: bool = True,
# ) -> Tuple[Optional[np.ndarray], bool, float]:
#     """Return (embedding, is_important, score)
    
#     Analyzes message importance using semantic similarity and keywords.
#     Overrides with user rules if provided and matching. Caches results.
#     """
#     if not text or not text.strip():
#         return None, False, 0.0

#     text_lower = text.lower().strip()
#     embedding = None  # Init here: Safe default, assigned later if needed
    
#     # Cache (unchanged, but use hashlib)
#     cache_key = f"msg_imp:{hashlib.md5(text_lower.encode()).hexdigest()[:12]}"
#     if user_rules:
#         rules_summary = str([(r.id, r.value) for r in user_rules])
#         rules_hash = hashlib.md5(rules_summary.encode()).hexdigest()[:8]
#         cache_key += f":{rules_hash}"
#     if sender_email:
#         cache_key += f":{hashlib.md5(sender_email.lower().encode()).hexdigest()[:8]}"
    
#     cached = cache.get(cache_key)
#     if cached:
#         return cached

#     # Rules override (enhanced with sender)
#     rule_score = None
#     needs_embedding = compute_embedding  # Track if we still need it
#     if user_rules:
#         max_importance = "low"
#         for rule in [r for r in user_rules if r.is_active]:
#             if rule.channel and rule.channel != "all":
#                 continue
            
#             match = False
#             if rule.rule_type in ["keyword", "body", "subject"]:
#                 if rule.value and rule.value.lower() in text_lower:
#                     match = True
#             elif rule.rule_type == "sender":
#                 if sender_email and rule.value and rule.value.lower() in sender_email.lower():
#                     match = True
#             elif rule.rule_type in ["attachment", "reply"]:
#                 continue  # Stubs
#             elif rule.rule_type == "ai":
#                 if rule.value and rule.value.lower() in text_lower:
#                     match = True
            
#             if match:
#                 if rule.importance == "critical":
#                     max_importance = "critical"
#                 elif rule.importance == "high" and max_importance != "critical":
#                     max_importance = "high"
#                 elif rule.importance == "medium" and max_importance != "high":
#                     max_importance = "medium"
        
#         importance_map = {"low": 0.2, "medium": 0.55, "high": 0.75, "critical": 0.95}
#         rule_score = importance_map.get(max_importance, 0.5)
#         if rule_score:
#             needs_embedding = False  # Rules hit: No need for semantic

#     # Fallback: Semantic + fuzzy keywords (only if needed)
#     combined = rule_score or 0.0  # Default low if no rules
#     if needs_embedding:
#         encode_start = time.perf_counter()
#         try:
#             embedding = model.encode([text])
#             print(f"DEBUG: Encoded in {time.perf_counter() - encode_start:.3f}s")  # Optional log
#         except Exception as e:
#             print(f"⚠️ Encoding failed: {e}")
#             embedding = None

#     if embedding is not None:
#         # Fuzzy keywords
#         kw_matches = sum(1 for kw in IMPORTANT_KEYWORDS if kw in text_lower)
#         keyword_score = min(kw_matches / max(len(IMPORTANT_KEYWORDS) * 0.3, 1), 1.0)
        
#         semantic_score = float(np.max(cosine_similarity(embedding, important_example_embeddings)))
#         # Blend: Use semantic/keywords if no rules, else stick to rule_score
#         if rule_score is None:
#             combined = keyword_weight * keyword_score + semantic_weight * semantic_score
#     else:
#         # No embedding: Keyword fallback
#         keyword_score = 1.0 if any(kw in text_lower for kw in IMPORTANT_KEYWORDS) else 0.0
#         if rule_score is None:
#             combined = keyword_weight * keyword_score

#     is_important = combined >= threshold

#     # Cache
#     cache.set(cache_key, (embedding, is_important, combined), 300)
#     return embedding, is_important, combined




import os
import google.generativeai as genai
from sklearn.metrics.pairwise import cosine_similarity  # Removed: no longer needed
import numpy as np
from typing import List, Optional, Tuple
from django.core.cache import cache
import hashlib  # For md5 hashing
import time  # For optional timing

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

IMPORTANT_KEYWORDS = [
    "urgent", "action required", "meeting", "deadline", "CEO", "important",
    "follow up", "please review", "immediate attention", "project", "money",
    "credit alert", "transaction successful"
]

def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding using Gemini embedding model."""
    if not text or not text.strip():
        return None
    try:
        result = genai.embed_content(
            model="models/embedding-001",
            content=text,
            task_type="SEMANTIC_SIMILARITY"
        )
        return result.embedding
    except Exception as e:
        print(f"⚠️ Embedding failed: {e}")
        return None

def get_importance_score(text: str) -> float:
    """Get importance score using Gemini."""
    prompt = f"""Rate the importance of this email message on a scale from 0.0 to 1.0.
0.0: Not important at all.
1.0: Extremely important, requires immediate attention.

Respond with ONLY the number, e.g., 0.85

Message:
{text}"""
    try:
        response = genai.generate_content(
            prompt,
            model="gemini-1.5-flash",
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=10,
            ),
        )
        score_str = response.text.strip()
        score = float(score_str)
        return max(0.0, min(1.0, score))
    except Exception as e:
        print(f"⚠️ Score generation failed: {e}")
        return 0.0

def is_message_important(
    text: str,
    user_rules: Optional[List['UserRule']] = None,
    sender_email: Optional[str] = None,
    keyword_weight: float = 0.4,
    semantic_weight: float = 0.6,
    threshold: float = 0.7,
    compute_embedding: bool = True,
) -> Tuple[Optional[np.ndarray], bool, float]:
    """Return (embedding, is_important, score)
    
    Analyzes message importance using Gemini for semantic scoring and keywords.
    Overrides with user rules if provided and matching. Caches results.
    """
    if not text or not text.strip():
        return None, False, 0.0

    text_lower = text.lower().strip()
    embedding = None
    
    # Cache (unchanged, but use hashlib)
    cache_key = f"msg_imp:{hashlib.md5(text_lower.encode()).hexdigest()[:12]}"
    if user_rules:
        rules_summary = str([(r.id, r.value) for r in user_rules])
        rules_hash = hashlib.md5(rules_summary.encode()).hexdigest()[:8]
        cache_key += f":{rules_hash}"
    if sender_email:
        cache_key += f":{hashlib.md5(sender_email.lower().encode()).hexdigest()[:8]}"
    
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Rules override (enhanced with sender)
    rule_score = None
    needs_embedding = compute_embedding
    if user_rules:
        max_importance = "low"
        for rule in [r for r in user_rules if r.is_active]:
            if rule.channel and rule.channel != "all":
                continue
            
            match = False
            if rule.rule_type in ["keyword", "body", "subject"]:
                if rule.value and rule.value.lower() in text_lower:
                    match = True
            elif rule.rule_type == "sender":
                if sender_email and rule.value and rule.value.lower() in sender_email.lower():
                    match = True
            elif rule.rule_type in ["attachment", "reply"]:
                continue  # Stubs
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
        if rule_score:
            needs_embedding = False

    # Initialize scores
    keyword_score = 0.0
    semantic_score = 0.0

    # Fallback: Semantic + fuzzy keywords (only if needed)
    if needs_embedding:
        analysis_start = time.perf_counter()
        emb_vec = get_embedding(text)
        if emb_vec is not None:
            embedding = np.array([emb_vec])
            # Fuzzy keywords
            kw_matches = sum(1 for kw in IMPORTANT_KEYWORDS if kw in text_lower)
            keyword_score = min(kw_matches / max(len(IMPORTANT_KEYWORDS) * 0.3, 1), 1.0)
            
            # Gemini importance score
            semantic_score = get_importance_score(text)
            print(f"DEBUG: Analyzed in {time.perf_counter() - analysis_start:.3f}s")  # Optional log
        else:
            print(f"⚠️ Embedding failed, using fallback")
            # Binary keywords
            keyword_score = 1.0 if any(kw in text_lower for kw in IMPORTANT_KEYWORDS) else 0.0
            semantic_score = 0.0
    else:
        # Binary keywords fallback
        keyword_score = 1.0 if any(kw in text_lower for kw in IMPORTANT_KEYWORDS) else 0.0
        semantic_score = 0.0

    combined = rule_score or 0.0
    if rule_score is None:
        combined = keyword_weight * keyword_score + semantic_weight * semantic_score

    is_important = combined >= threshold

    # Cache
    cache.set(cache_key, (embedding, is_important, combined), 300)
    return embedding, is_important, combined