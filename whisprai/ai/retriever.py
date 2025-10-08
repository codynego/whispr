# core/ai/retriever.py
import numpy as np
from django.db import connection
from emails.models import Email
from core.ai.embeddings import get_text_embedding

def cosine_similarity(vec_a, vec_b):
    return np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))

def retrieve_relevant_emails(user, query, limit=5):
    """Retrieve top N emails by vector similarity."""
    query_embedding = get_text_embedding(query)
    if not query_embedding:
        return Email.objects.filter(user=user).order_by('-received_at')[:limit]

    if connection.vendor == 'postgresql':
        # PostgreSQL with pgvector: use <=> for cosine distance
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id FROM emails_email
                WHERE user_id = %s AND embedding IS NOT NULL
                ORDER BY embedding <=> %s
                LIMIT %s;
            """, [user.id, query_embedding, limit])
            ids = [row[0] for row in cursor.fetchall()]
        return Email.objects.filter(id__in=ids)

    else:
        # SQLite fallback: use numpy for local similarity
        all_emails = Email.objects.filter(accouser=user, embedding__isnull=False)
        scored = []
        for e in all_emails:
            score = cosine_similarity(np.array(e.embedding), np.array(query_embedding))
            scored.append((score, e))
        return [e for _, e in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]
