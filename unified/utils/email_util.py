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
import email.header
import re
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from unified.utils.common_utils import is_message_important
from unified.models import ChannelAccount, Message, Conversation 
from unified.models import UserRule
from celery import shared_task

logger = logging.getLogger(__name__)


# === Gmail Helpers ===
def decode_base64_data(data):
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def clean_sender_field(raw_value):
    if not raw_value:
        return None, None
    name, addr = email.utils.parseaddr(raw_value)
    if not addr:
        match = re.search(r'<?([\w\.-]+@[\w\.-]+)>?', raw_value)
        addr = match.group(1) if match else None
    if name and name.startswith("=?"):
        try:
            name = str(email.header.make_header(email.header.decode_header(name)))
        except Exception:
            pass
    name = name.strip('"') if name else None
    return name or None, addr or None


def extract_bodies_recursive(payload):
    plain, html = "", ""
    mime_type = payload.get("mimeType")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        plain += decode_base64_data(body_data)
    elif mime_type == "text/html" and body_data:
        html += decode_base64_data(body_data)

    for part in payload.get("parts", []) or []:
        sub_plain, sub_html = extract_bodies_recursive(part)
        plain += "\n" + sub_plain
        html += "\n" + sub_html

    return plain.strip(), html.strip()


def parse_gmail_date(date_str):
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        if parsed and not timezone.is_aware(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
    except Exception:
        return timezone.now()


def fetch_gmail_messages(account: ChannelAccount, limit=10):
    """
    Fetch and store latest Gmail messages for a ChannelAccount.
    Automatically attaches messages to a Conversation (thread).
    Includes both plain text and HTML body in metadata.
    """
    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
    )
    user_rule = UserRule.objects.filter(user=account__user)

    service = build("gmail", "v1", credentials=creds)
    results = service.users().messages().list(userId="me", maxResults=limit).execute()
    messages = results.get("messages", [])
    synced = 0

    for msg in messages:
        msg_detail = service.users().messages().get(userId="me", id=msg["id"]).execute()
        payload = msg_detail.get("payload", {})
        headers = payload.get("headers", [])

        # === Normalize headers ===
        header_map = {h["name"].lower(): h["value"] for h in headers}
        subject = header_map.get("subject", "")
        from_raw = header_map.get("from", "")
        to_raw = header_map.get("to", "")
        date_raw = header_map.get("date", "")

        sender_name, sender_email = clean_sender_field(from_raw)
        _, recipient_email = clean_sender_field(to_raw)
        snippet = msg_detail.get("snippet", "")
        plain_body, html_body = extract_bodies_recursive(payload)
        received_at = parse_gmail_date(date_raw)
        thread_id = msg_detail.get("threadId")

        # === Conversation handling ===
        conversation, _ = Conversation.objects.get_or_create(
            account=account,
            thread_id=thread_id,
            defaults={
                "channel": "email",
                "title": subject[:200] or "No Subject",
                "last_message_at": received_at,
                "last_sender": sender_email,
            },
        )

        # Update conversation if newer message arrives
        if not conversation.last_message_at or received_at > conversation.last_message_at:
            conversation.last_message_at = received_at
            conversation.last_sender = sender_email
            if subject:
                conversation.title = subject[:200]
            conversation.save(update_fields=["last_message_at", "last_sender", "title", "updated_at"])

        # === Analyze importance ===
        _, is_important, score = is_message_important(f"{subject} {snippet}", user_rule)

        # === Save message ===
        Message.objects.update_or_create(
            account=account,
            conversation=conversation,
            external_id=msg["id"],
            defaults={
                "channel": "email",
                "sender": sender_email,
                "sender_name": sender_name,
                "recipients": [recipient_email] if recipient_email else [],
                "content": plain_body or snippet,
                # ✅ Save subject, raw Gmail data, and HTML body in metadata
                "metadata": {
                    "subject": subject,
                    "html_body": html_body,
                },
                "attachments": [],
                "importance": "high" if is_important else "medium",
                "importance_score": score,
                "is_read": "UNREAD" not in msg_detail.get("labelIds", []),
                "is_incoming": True,
                "sent_at": received_at,
            },
        )

        synced += 1

    logger.info(f"✅ Synced {synced} Gmail messages for {account.address_or_id}")
    return synced


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
def send_gmail_email(self, account, to_email, subject, body, body_html=None, attachments=None, thread_id=None):
    """Send email using Gmail API."""
    print("got to this point")
    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
    )
    service = build("gmail", "v1", credentials=creds)

    if isinstance(to_email, str):
        to_email = [to_email]

    if body_html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "plain"))
        msg.attach(MIMEText(body_html, "html"))
    else:
        msg = MIMEText(body, "plain")

    msg["to"] = ", ".join(to_email)
    msg["subject"] = subject

    # Attachments
    if attachments:
        if not isinstance(msg, MIMEMultipart):
            msg_full = MIMEMultipart()
            msg_full.attach(MIMEText(body, "plain"))
            msg = msg_full

        for file_path in attachments:
            content_type, encoding = mimetypes.guess_type(file_path)
            if content_type is None or encoding is not None:
                content_type = "application/octet-stream"
            main_type, sub_type = content_type.split("/", 1)
            with open(file_path, "rb") as f:
                mime_part = MIMEBase(main_type, sub_type)
                mime_part.set_payload(f.read())
                encoders.encode_base64(mime_part)
                mime_part.add_header("Content-Disposition", f"attachment; filename={file_path.split('/')[-1]}")
                msg.attach(mime_part)

    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    message_data = {"raw": raw_message}
    if thread_id:
        message_data["threadId"] = thread_id

    try:
        sent = service.users().messages().send(userId="me", body=message_data).execute()
        logger.info(f"📤 Sent email to {to_email}: {subject}")
        return sent
    except Exception as e:
        logger.error(f"⚠️ Failed to send email: {e}")
        return None
