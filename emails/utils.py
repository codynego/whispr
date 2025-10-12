# email_importance.py
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import base64
import email.utils
import re

from .models import Email


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






def decode_base64_data(data):
    """Safely decode base64 email content."""
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def clean_sender_field(raw_value):
    """
    Extract name + clean email from something like:
    'Alex Berman <alex@x27.io>' or '"Alex Berman" <alex@x27.io>'
    Returns: (name, email)
    """
    if not raw_value:
        return None, None

    name, addr = email.utils.parseaddr(raw_value)
    # Fallback cleanup if parseaddr fails
    if not addr:
        match = re.search(r'<?([\w\.-]+@[\w\.-]+)>?', raw_value)
        addr = match.group(1) if match else None

    # Decode quoted names like =?UTF-8?B?...?=
    if name and name.startswith("=?"):
        try:
            name = str(email.header.make_header(email.header.decode_header(name)))
        except Exception:
            pass

    # Final cleanup
    name = name.strip('"') if name else None
    return name or None, addr or None


def extract_bodies_recursive(payload):
    """
    Recursively extract plain and HTML bodies from Gmail message payloads.
    """
    plain_body = ""
    html_body = ""

    mime_type = payload.get("mimeType")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        plain_body += decode_base64_data(body_data)
    elif mime_type == "text/html" and body_data:
        html_body += decode_base64_data(body_data)

    for part in payload.get("parts", []) or []:
        sub_plain, sub_html = extract_bodies_recursive(part)
        plain_body += "\n" + sub_plain
        html_body += "\n" + sub_html

    return plain_body.strip(), html_body.strip()


def parse_gmail_date(date_str):
    """Convert Gmail date string → timezone-aware datetime."""
    from datetime import datetime
    try:
        parsed_date = email.utils.parsedate_to_datetime(date_str)
        if parsed_date and not timezone.is_aware(parsed_date):
            parsed_date = timezone.make_aware(parsed_date)
        return parsed_date
    except Exception:
        return timezone.now()


def fetch_gmail_emails(account):
    """
    Fetch and store latest Gmail messages for an account.
    """
    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
    )

    service = build("gmail", "v1", credentials=creds)
    results = service.users().messages().list(userId="me", maxResults=10).execute()
    messages = results.get("messages", [])

    count = 0

    for msg in messages:
        msg_detail = service.users().messages().get(userId="me", id=msg["id"]).execute()
        payload = msg_detail.get("payload", {})
        headers = payload.get("headers", [])

        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
        from_raw = next((h["value"] for h in headers if h["name"] == "From"), "")
        to_raw = next((h["value"] for h in headers if h["name"] == "To"), "")
        date_raw = next((h["value"] for h in headers if h["name"] == "Date"), "")

        sender_name, sender_email = clean_sender_field(from_raw)
        print(f"Processing email from {sender_email} with subject '{sender_name}'")
        _, recipient_email = clean_sender_field(to_raw)
        snippet = msg_detail.get("snippet", "")

        plain_body, html_body = extract_bodies_recursive(payload)
        received_at = parse_gmail_date(date_raw)

        Email.objects.update_or_create(
            account=account,
            message_id=msg["id"],
            defaults={
                "thread_id": msg_detail.get("threadId"),
                "sender_name": sender_name,
                "sender": sender_email or "",
                "recipient": recipient_email or "",
                "subject": subject,
                "snippet": snippet,
                "body": plain_body,
                "body_html": html_body,
                "received_at": received_at,
            },
        )
        count += 1

    return count
