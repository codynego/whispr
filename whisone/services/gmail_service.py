import base64
from datetime import datetime
from typing import List, Dict

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

class GmailService:
    def __init__(self, access_token: str, refresh_token: str, client_id: str, client_secret: str):
        self.creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token"
        )
        self.service = build('gmail', 'v1', credentials=self.creds)

    # -----------------------------
    # Fetch emails
    # -----------------------------
    def fetch_emails(
        self,
        query: str = "",
        after: datetime = None,
        before: datetime = None,
        unread_only: bool = False,
        max_results: int = 10
    ) -> List[Dict]:
        q = query
        if unread_only:
            q += " is:unread"
        if after:
            q += f" after:{after.strftime('%Y/%m/%d')}"
        if before:
            q += f" before:{before.strftime('%Y/%m/%d')}"

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
                "body": body_data
            })
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

    # -----------------------------
    # Reply to email
    # -----------------------------
    def reply_email(self, msg_id: str, body: str):
        # Get original email headers
        original = self.service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['Subject','From','To','Message-ID']).execute()
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
