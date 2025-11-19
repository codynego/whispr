
import base64
from datetime import datetime
from typing import List, Dict
from django.core.cache import cache  # Django cache
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

User = get_user_model()


class GmailService:
    def __init__(self, access_token: str, refresh_token: str, client_id: str, client_secret: str, user_email: str = None):
        self.user_email = user_email  # Store for cache key
        self.creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        self.service = build('gmail', 'v1', credentials=self.creds)


    # -----------------------------
    # Fetch emails with caching
    # -----------------------------
    def fetch_emails(
        self,
        query: str = "",
        after: datetime = None,
        before: datetime = None,
        unread_only: bool = False,
        max_results: int = 10,
        cache_timeout: int = 300  # default 5 minutes
    ) -> List[Dict]:
        # Build a unique cache key based on user, query, and filters
        key_parts = [
            self.user_email or "default_user",
            query,
            str(after) if after else "",
            str(before) if before else "",
            str(unread_only),
            str(max_results)
        ]
        cache_key = "gmail_emails:" + ":".join(key_parts)

        # Try getting from cache
        cached_emails = cache.get(cache_key)
        if cached_emails:
            return cached_emails

        # Build Gmail query
        q = query
        if unread_only:
            q += " is:unread"
        if after:
            q += f" after:{after.strftime('%Y/%m/%d')}"
        if before:
            q += f" before:{before.strftime('%Y/%m/%d')}"

        # Fetch from Gmail API
        result = self.service.users().messages().list(userId='me', q=q, maxResults=max_results).execute()
        messages = []
        for msg in result.get('messages', []):
            msg_detail = self.service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            payload = msg_detail['payload']
            headers = {h['name']: h['value'] for h in payload.get('headers', [])}

            body_data = ""
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                        body_data += base64.urlsafe_b64decode(part['body']['data']).decode()
            else:
                if 'body' in payload and 'data' in payload['body']:
                    body_data = base64.urlsafe_b64decode(payload['body']['data']).decode()

            messages.append({
                "id": msg['id'],
                "subject": headers.get('Subject', ''),
                "from": headers.get('From', ''),
                "to": headers.get('To', ''),
                "date": headers.get('Date', ''),
                "snippet": msg_detail.get('snippet', ''),
                "body": body_data,
                "unread": "UNREAD" in [label for label in msg_detail.get('labelIds', [])]
            })

        # Save to cache
        cache.set(cache_key, messages, timeout=cache_timeout)
        return messages

    # -----------------------------
    # Mark as read/unread
    # -----------------------------
    def mark_as_read(self, msg_id: str):
        self.service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    def mark_as_unread(self, msg_id: str):
        self.service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={"addLabelIds": ["UNREAD"]}
        ).execute()

    # -----------------------------
    # Move email to label
    # -----------------------------
    def move_to_label(self, msg_id: str, label_id: str):
        self.service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={"addLabelIds": [label_id]}
        ).execute()

    # -----------------------------
    # Delete email
    # -----------------------------
    def delete_email(self, msg_id: str):
        self.service.users().messages().delete(
            userId='me',
            id=msg_id
        ).execute()

    def get_emails_last_24h(self, max_results=10):
        after = datetime.utcnow() - timedelta(hours=24)

        return self.fetch_emails(
            query="label:important",
            after=after,
            unread_only=False,
            max_results=max_results
        )

    # -----------------------------
    # Fetch unread "important" emails
    # (Google marks emails with the IMPORTANT label)
    # -----------------------------
    def get_important_unread(self, max_results=5):
        return self.fetch_emails(
            query="label:important",
            unread_only=True,
            max_results=max_results
        )

    # -----------------------------
    # Fetch today's emails only
    # -----------------------------
    def get_today_emails(self, max_results=10):
        now = datetime.utcnow()
        start_of_day = datetime(now.year, now.month, now.day)

        return self.fetch_emails(
            query="",
            after=start_of_day,
            unread_only=False,
            max_results=max_results
        )

        # -----------------------------
    # Fetch IMPORTANT emails + optional search query
    # -----------------------------
    def fetch_important_emails(
        self,
        query: str = "",              # e.g. "invoice", "from:netflix", "refund", etc.
        unread_only: bool = False,
        after: datetime = None,
        before: datetime = None,
        max_results: int = 10,
        cache_timeout: int = 300
    ) -> List[Dict]:
        """
        Fetch only emails marked as IMPORTANT by Gmail's AI,
        with optional additional keyword filtering.
        """
        # Build cache key
        cache_key = (
            f"gmail_important:{self.user_email or 'user'}:"
            f"q={query.strip()}:unread={unread_only}:"
            f"after={after}:before={before}:max={max_results}"
        )

        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # Always start with Gmail's IMPORTANT system label
        # q_parts = ["label:PRIMARY"]

        # Add user's custom query (if any)
        if query.strip():
            q_parts.append(query.strip())

        # Add filters
        if unread_only:
            q_parts.append("is:unread")
        if after:
            q_parts.append(f"after:{after.strftime('%Y/%m/%d')}")
        if before:
            q_parts.append(f"before:{before.strftime('%Y/%m/%d')}")

        final_query = " ".join(q_parts)

        try:
            response = self.service.users().messages().list(
                userId='me',
                q=final_query,
                maxResults=max_results
            ).execute()

            messages = response.get('messages', [])
            emails = []

            for msg in messages:
                msg_detail = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()

                payload = msg_detail['payload']
                headers = {h['name']: h['value'] for h in payload.get('headers', [])}

                # Extract plain text body
                body = ""
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part.get('mimeType') == 'text/plain' and part['body'].get('data'):
                            body += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            break
                elif payload.get('mimeType') == 'text/plain' and payload['body'].get('data'):
                    body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

                # Optional: limit body size
                if len(body) > 1500:
                    body = body[:1500] + "..."

                emails.append({
                    "id": msg['id'],
                    "threadId": msg_detail.get('threadId'),
                    "subject": headers.get('Subject', '(no subject)'),
                    "from": headers.get('From', 'Unknown'),
                    "date": headers.get('Date', ''),
                    "snippet": msg_detail.get('snippet', ''),
                    "body_preview": body.strip(),
                    "is_unread": 'UNREAD' in msg_detail.get('labelIds', []),
                    "labels": msg_detail.get('labelIds', []),
                })

            cache.set(cache_key, emails, timeout=cache_timeout)
            return emails

        except Exception as e:
            print(f"[GmailService] Error fetching important emails: {e}")
            return []

    # -----------------------------
    # Convenient wrappers
    # -----------------------------
    def get_important_unread(self, max_results: int = 10) -> List[Dict]:
        return self.fetch_important_emails(unread_only=True, max_results=max_results)

    def search_important(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search within important emails only"""
        return self.fetch_important_emails(query=query, max_results=max_results)

    def get_important_today(self, max_results: int = 10) -> List[Dict]:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.fetch_important_emails(after=today, max_results=max_results)

    # -----------------------------
    # Reply to email
    # -----------------------------
    def reply_email(self, msg_id: str, body: str):
        original = self.service.users().messages().get(
            userId='me', id=msg_id, format='metadata',
            metadataHeaders=['Subject','From','To','Message-ID']
        ).execute()
        headers = {h['name']: h['value'] for h in original['payload']['headers']}

        from email.mime.text import MIMEText
        import base64

        reply = MIMEText(body)
        reply['To'] = headers['From']
        reply['From'] = headers['To']
        reply['Subject'] = "Re: " + headers.get('Subject', '')
        reply['In-Reply-To'] = headers.get('Message-ID', '')
        raw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
        message = {'raw': raw, 'threadId': original.get('threadId')}
        self.service.users().messages().send(userId='me', body=message).execute()