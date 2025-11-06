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
from google.auth.transport.requests import Request
from typing import List, Dict, Any

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


def fetch_gmail_messages(account_id: int, limit=20) -> int:
    """
    Fetch full Gmail message details (including bodies).
    Does NOT store anything — passes data to Celery for storage.
    """
    print(f"DEBUG: Entering fetch_gmail_messages with account_id={account_id}, limit={limit}")
    
    account = ChannelAccount.objects.get(id=account_id, is_active=True)
    print(f"DEBUG: Retrieved account {account.id} - {account.address_or_id}")
    
    logger.info(f"🔍 Fetching Gmail messages for {account.address_or_id}")

    creds = Credentials(
        token=account.access_token,
        refresh_token=account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
    )
    print(f"DEBUG: Created credentials object for account {account_id}")

    if not creds.valid and creds.refresh_token:
        print(f"DEBUG: Credentials invalid, refreshing for account {account_id}")
        creds.refresh(Request())
        account.access_token = creds.token
        account.save(update_fields=["access_token"])
        print(f"DEBUG: Refreshed and saved new access token for account {account_id}")

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    print(f"DEBUG: Built Gmail service for account {account_id}")

    message_ids: List[str] = []
    full_messages: List[Dict[str, Any]] = []
    
    if not account.last_history_id:
        # First sync
        print(f"DEBUG: Starting first sync for account {account_id}")
        logger.info(f"🆕 First Gmail sync for {account.address_or_id}")
        resp = service.users().messages().list(userId="me", maxResults=limit).execute()
        print(f"DEBUG: List response keys: {list(resp.keys())}")
        message_ids = [m["id"] for m in resp.get("messages", [])]
        print(f"DEBUG: Extracted {len(message_ids)} message IDs: {message_ids}")
        logger.info(f"Fetched {len(message_ids)} initial Gmail message IDs")

        # Fetch full details for each
        for msg_id in message_ids:  # Fixed: was message_keys()
            print(f"DEBUG: Fetching full details for message {msg_id}")
            try:
                msg_detail = service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()
                print(f"DEBUG: Full message keys for {msg_id}: {list(msg_detail.keys())}")
                full_messages.append(msg_detail)
                logger.debug(f"Fetched full details for message {msg_id}")
            except Exception as e:
                print(f"DEBUG: Exception fetching {msg_id}: {type(e).__name__}: {e}")
                logger.warning(f"Failed to fetch full details for {msg_id}: {e}")
                continue

        # Save last history ID
        print(f"DEBUG: Fetching profile for history ID")
        profile = service.users().getProfile(userId="me").execute()
        print(f"DEBUG: Profile historyId: {profile.get('historyId')}")
        account.last_history_id = profile.get("historyId")
        account.save(update_fields=["last_history_id"])
        print(f"DEBUG: Saved last_history_id={account.last_history_id} for account {account_id}")

    else:
        # Incremental sync
        print(f"DEBUG: Starting incremental sync with last_history_id={account.last_history_id}")
        try:
            history = service.users().history().list(
                userId="me", startHistoryId=account.last_history_id
            ).execute()
            print(f"DEBUG: History response keys: {list(history.keys())}")
            print(f"DEBUG: Number of histories: {len(history.get('history', []))}")
            histories = history.get("history", [])
            message_ids = {
                m["message"]["id"] for h in histories for m in h.get("messagesAdded", [])
            }
            print(f"DEBUG: Extracted {len(message_ids)} incremental message IDs: {list(message_ids)}")
            logger.info(f"Fetched {len(message_ids)} incremental Gmail message IDs")

            # Fetch full details for each
            for msg_id in message_ids:
                print(f"DEBUG: Fetching full details for incremental message {msg_id}")
                try:
                    msg_detail = service.users().messages().get(
                        userId="me", id=msg_id, format="full"
                    ).execute()
                    print(f"DEBUG: Full message keys for {msg_id}: {list(msg_detail.keys())}")
                    full_messages.append(msg_detail)
                    logger.debug(f"Fetched full details for message {msg_id}")
                except Exception as e:
                    print(f"DEBUG: Exception fetching incremental {msg_id}: {type(e).__name__}: {e}")
                    logger.warning(f"Failed to fetch full details for {msg_id}: {e}")
                    continue

            new_history_id = history.get("historyId")
            print(f"DEBUG: New history ID: {new_history_id}")
            if new_history_id:
                account.last_history_id = new_history_id
                account.save(update_fields=["last_history_id"])
                print(f"DEBUG: Updated last_history_id to {new_history_id} for account {account_id}")
        except Exception as e:
            print(f"DEBUG: Exception in incremental sync: {type(e).__name__}: {e}")
            logger.warning(f"⚠️ History expired for {account.address_or_id}, resetting: {e}")
            account.last_history_id = None
            account.save(update_fields=["last_history_id"])
            print(f"DEBUG: Reset last_history_id to None and recursing")
            return fetch_gmail_messages(account_id, limit)

    print(f"DEBUG: Total full_messages collected: {len(full_messages)}")
    
    if full_messages:
        # Hand off to Celery for background storage
        print(f"DEBUG: Delaying store_gmail_messages task with {len(full_messages)} messages")
        store_gmail_messages.delay(account_id, full_messages)
        print(f"DEBUG: Task delayed successfully")
        return len(full_messages)
    print(f"DEBUG: No full messages to process, returning 0")
    return 0


# ==============================================================
# ✅ Celery task: Store full Gmail messages (no API calls)
# ==============================================================

@shared_task(
    bind=True,
    soft_time_limit=300,  # 5 min soft
    time_limit=360,  # 6 min hard
    autoretry_for=(Exception,),
    max_retries=3
)
def store_gmail_messages(self, account_id: int, message_details_list: List[Dict[str, Any]]) -> None:
    """
    Parses and stores a list of full Gmail message details for the given account.
    No API calls — uses pre-fetched data.
    """
    print(f"DEBUG: Entering store_gmail_messages task for account {account_id} with {len(message_details_list)} messages")
    print(f"DEBUG: Task ID: {self.request.id}")

    account = ChannelAccount.objects.get(id=account_id, is_active=True)
    print(f"DEBUG: Retrieved account {account.id} - {account.address_or_id}")
    
    user_rules = UserRule.objects.filter(user=account.user)
    print(f"DEBUG: Retrieved {len(user_rules)} user rules")

    processed_count = 0
    for idx, msg_detail in enumerate(message_details_list):
        print(f"DEBUG: Processing message {idx + 1}/{len(message_details_list)} for ID: {msg_detail.get('id', 'UNKNOWN')}")

        payload = msg_detail.get("payload", {})
        print(f"DEBUG: Payload keys: {list(payload.keys())}")
        
        headers = payload.get("headers", [])
        print(f"DEBUG: Number of headers: {len(headers)}")
        header_map = {h["name"].lower(): h["value"] for h in headers}
        print(f"DEBUG: Header keys in map: {list(header_map.keys())}")

        subject = header_map.get("subject", "")
        print(f"DEBUG: Subject: {subject[:50]}..." if len(subject) > 50 else f"DEBUG: Subject: {subject}")
        
        from_raw = header_map.get("from", "")
        to_raw = header_map.get("to", "")
        date_raw = header_map.get("date", "")
        print(f"DEBUG: From raw: {from_raw}")
        print(f"DEBUG: To raw: {to_raw}")
        print(f"DEBUG: Date raw: {date_raw}")

        sender_name, sender_email = clean_sender_field(from_raw)
        print(f"DEBUG: Parsed sender - name: {sender_name}, email: {sender_email}")
        
        _, recipient_email = clean_sender_field(to_raw)
        print(f"DEBUG: Parsed recipient email: {recipient_email}")
        
        snippet = msg_detail.get("snippet", "")
        print(f"DEBUG: Snippet preview: {snippet[:50]}...")
        
        plain_body, html_body = extract_bodies_recursive(payload)
        print(f"DEBUG: Extracted bodies - plain len: {len(plain_body or '')}, html len: {len(html_body or '')}")
        
        received_at = parse_gmail_date(date_raw)
        print(f"DEBUG: Parsed received_at: {received_at}")
        
        thread_id = msg_detail.get("threadId")
        print(f"DEBUG: Thread ID: {thread_id}")

        # _, is_important, score = is_message_important(f"{subject} {snippet}", user_rules)
        is_important = True
        score = 0.9
        print(f"DEBUG: Message importance for ID {msg_detail.get('id')}: is_important={is_important}, score={score}")

        # Conversation handling
        print(f"DEBUG: Getting or creating conversation for thread {thread_id}")
        conversation, created = Conversation.objects.get_or_create(
            account=account,
            thread_id=thread_id,
            defaults={
                "channel": "email",
                "title": subject[:200] or "No Subject",
                "last_message_at": received_at,
                "last_sender": sender_email,
            },
        )
        print(f"DEBUG: Conversation {conversation.id} - created: {created}, title: {conversation.title}")

        if not created and (not conversation.last_message_at or received_at > conversation.last_message_at):
            print(f"DEBUG: Updating conversation last_message_at from {conversation.last_message_at} to {received_at}")
            conversation.last_message_at = received_at
            conversation.last_sender = sender_email
            if subject:
                conversation.title = subject[:200]
            conversation.save(update_fields=["last_message_at", "last_sender", "title", "updated_at"])
            print(f"DEBUG: Conversation updated successfully")

        print(f"DEBUG: Updating or creating Message for external_id {msg_detail.get('id')}")
        message_obj, created_msg = Message.objects.update_or_create(
            account=account,
            conversation=conversation,
            external_id=msg_detail["id"],
            defaults={
                "channel": "email",
                "sender": sender_email,
                "sender_name": sender_name,
                "recipients": [recipient_email] if recipient_email else [],
                "content": plain_body or snippet,
                "metadata": {"subject": subject, "html_body": html_body},
                "attachments": [],  # TODO: Parse attachments from payload if needed
                "importance": "high" if is_important else "medium",
                "importance_score": score,
                "is_read": "UNREAD" not in msg_detail.get("labelIds", []),
                "is_incoming": True,
                "sent_at": received_at,
            },
        )
        print(f"DEBUG: Message {message_obj.id} - created: {created_msg}")

        processed_count += 1
        print(f"DEBUG: Successfully processed message {msg_detail.get('id')}")

    print(f"DEBUG: Task completed - processed {processed_count} messages successfully.")


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