# core/ai/retriever.py
from emails.models import Email
from django.db.models import Q

def retrieve_relevant_emails(user, query, limit=5):
    """
    Retrieve emails related to the query using keyword matching.
    Later, you can replace this with vector embeddings.
    """
    keywords = query.lower().split()
    filters = Q()
    for kw in keywords:
        filters |= Q(subject__icontains=kw) | Q(body__icontains=kw) | Q(sender__icontains=kw)
    
    emails = Email.objects.filter(account__user=user).filter(filters).order_by('-received_at')[:limit]
    return emails



