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
from django.db import transaction

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
        store_gmail_messages(account_id, full_messages)
        print(f"DEBUG: Task delayed successfully")
        return len(full_messages)
    print(f"DEBUG: No full messages to process, returning 0")
    return 0


# ==============================================================
# ✅ Celery task: Store full Gmail messages (no API calls)
# ==============================================================

# @shared_task(name="store_gmail_messages")
import time
from django.db import transaction
from celery.exceptions import WorkerLostError

@shared_task(name="store_gmail_messages", bind=True)  # Add bind=True for self.retry if needed
def store_gmail_messages(self, account_id: int, message_details_list: List[Dict[str, Any]]) -> None:
    start_time = time.time()
    print(f"DEBUG: Starting store_gmail_messages_task for account {account_id} ({len(message_details_list)} messages) at {start_time}")

    try:
        with transaction.atomic():  # Wrap whole task in atomic for rollback on failure
            account_start = time.time()
            account = ChannelAccount.objects.select_related("user").get(id=account_id, is_active=True)
            print(f"DEBUG: Account get took {time.time() - account_start:.2f}s")

            rules_start = time.time()
            user_rules = list(UserRule.objects.filter(user=account.user))
            print(f"DEBUG: User rules query took {time.time() - rules_start:.2f}s - Found {len(user_rules)}")

            processed = 0
            for i, msg_detail in enumerate(message_details_list, 1):
                msg_start = time.time()
                msg_id = msg_detail.get("id")
                thread_id = msg_detail.get("threadId")
                payload = msg_detail.get("payload", {})
                headers = payload.get("headers", [])
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
                print(f"DEBUG: Processing msg {i}/{len(message_details_list)} ({msg_id}) at {time.time()}")

                # ... (your existing parsing code for subject, sender, etc.) ...
                is_important, score = True, 0.9
                print(f"DEBUG: Parsed headers for msg {msg_id} in {time.time() - msg_start:.2f}s")
                #_, is_important, score = is_message_important(plain_body or snippet, user_rules=user_rules)
                print(f"DEBUG: Importance analysis for msg {msg_id} in {time.time() - msg_start:.2f}s - Important: {is_important}, Score: {score}")
                

                conv_start = time.time()
                conversation = Conversation.objects.filter(account=account, thread_id=thread_id).first()
                if not conversation:
                    conversation = Conversation.objects.create(
                        account=account,
                        thread_id=thread_id,
                        channel="email",
                        title=subject[:200] or "No Subject",
                        last_message_at=received_at,
                        last_sender=sender_email,
                    )
                    print(f"DEBUG: Created new conversation for {thread_id}")
                else:
                    # Your update code
                    if not conversation.last_message_at or received_at > conversation.last_message_at:
                        conversation.last_message_at = received_at
                        conversation.last_sender = sender_email
                        conversation.title = subject[:200] or conversation.title
                        conversation.save(update_fields=["last_message_at", "last_sender", "title", "updated_at"])
                    print(f"DEBUG: Updated conversation {thread_id}")
                print(f"DEBUG: Conversation op took {time.time() - conv_start:.2f}s")

                msg_op_start = time.time()
                try:
                    print(f"DEBUG: About to run update_or_create for msg {msg_id} (thread {thread_id})")
                    print(f"DEBUG: Defaults preview: channel={sender_email[:20]}..., content_len={len(plain_body or snippet)}, sent_at={received_at}, is_read={ 'UNREAD' not in msg_detail.get('labelIds', []) }")  # Sanitize for logs
                    message = Message.objects.filter(
                        account=account,
                        external_id=msg_id
                    ).first()
                    # Split: Manual get_or_create to isolate SELECT vs INSERT
                    print(f"DEBUG: Fetched existing message for {msg_id}, now checking existence")
                    if not message:
                        msg_obj = Message.objects.create(
                            account=account,
                            conversation=conversation,
                            external_id=msg_id,
                            channel="email",
                            sender=sender_email,
                            sender_name=sender_name,
                            recipients=[recipient_email] if recipient_email else [],
                            content=plain_body or snippet,
                            metadata={"subject": subject, "html_body": html_body},
                            attachments=[],
                            importance="high" if is_important else "medium",
                            importance_score=score,
                            is_read="UNREAD" not in msg_detail.get("labelIds", []),
                            is_incoming=True,
                            sent_at=received_at,
                        )
                        print(f"DEBUG: get_or_create completed for {msg_id} - in {time.time() - msg_op_start:.2f}s")
                    else:
                        print(f"DEBUG: Message {msg_id} exists, updating fields if needed")
                        # Update existing message
                        updated = False
                        if message.content != (plain_body or snippet):
                            message.content = plain_body or snippet
                            updated = True
                        if message.sender != sender_email:
                            message.sender = sender_email
                            updated = True
                        if message.sent_at != received_at:
                            message.sent_at = received_at
                            updated = True
                        if not message.is_read and "UNREAD" not in msg_detail.get("labelIds", []):
                            message.is_read = True
                            updated = True
                        if updated:
                            message.metadata = {"subject": subject, "html_body": html_body}
                            message.importance = "high" if is_important else "medium"
                            message.importance_score = score
                            message.save()
                            print(f"DEBUG: Updated existing message {msg_id} in {time.time() - msg_op_start:.2f}s")
                        else:
                            print(f"DEBUG: No update needed for existing message {msg_id}")
                except Exception as e:
                    print(f"DEBUG: Message {msg_id} failed: {type(e).__name__}: {e}")
                    logger.error(f"Failed saving message {msg_id}: {e}")
                    raise  # Re-raise to trigger atomic rollback
                print(f"DEBUG: Message op took {time.time() - msg_op_start:.2f}s")

                processed += 1
                if processed % 5 == 0:  # More frequent logging
                    print(f"DEBUG: {processed} messages processed in {time.time() - start_time:.2f}s total")

            print(f"DEBUG: Task completed in {time.time() - start_time:.2f}s - Stored {processed} messages")
    except Exception as e:
        print(f"DEBUG: Task failed after {time.time() - start_time:.2f}s: {type(e).__name__}: {e}")
        logger.error(f"Store task failed for {account_id}: {e}", exc_info=True)
        self.retry(countdown=60 * 5, exc=e)  # Retry after 5min, adjust as needed


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