from celery import shared_task
from django.conf import settings
from django.utils import timezone
import openai
import logging
from .models import EmailAccount, Email

logger = logging.getLogger(__name__)

import logging
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.utils import timezone
from celery import shared_task

from .models import EmailAccount, Email  # your Django models

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
def sync_email_account(self, account_id):
    """
    Sync emails from Gmail or Outlook using stored tokens.
    """
    try:
        account = EmailAccount.objects.get(id=account_id)
        provider = account.provider.lower()

        if provider == "gmail":
            logger.info(f"Syncing Gmail account {account.email_address}")
            print("Syncing Gmail account", account.email_address)
            count = fetch_gmail_emails(account)
            print("Fetched", count, "messages for", account.email_address)
            logger.info(f"Fetched {count} messages for {account.email_address}")
            return {"status": "success", "count": count}

        elif provider == "outlook":
            logger.info(f"Syncing Outlook account {account.email_address}")
            # TODO: implement Outlook equivalent later
            return {"status": "success", "message": "Outlook sync not yet implemented"}

    except Exception as e:
        logger.error(f"Error syncing {account.provider} for user {account.user.id}: {str(e)}")
        return {"status": "error", "message": str(e)}



def fetch_gmail_emails(account):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import base64

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
        from_ = next((h["value"] for h in headers if h["name"] == "From"), "")
        snippet = msg_detail.get("snippet", "")

        body = ""
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        Email.objects.update_or_create(
            account=account,
            message_id=msg["id"],
            defaults={
                "sender": from_,
                "subject": subject,
                "snippet": snippet,
                "body": body,
                "received_at": timezone.now(),
            },
        )
        count += 1

    return count


# === Placeholder for Outlook ===
def exchange_outlook_auth_code(auth_code):
    # TODO: Implement Microsoft Graph token exchange here
    return {"access_token": "OUTLOOK_ACCESS", "refresh_token": "OUTLOOK_REFRESH"}


def fetch_outlook_emails(account):
    # TODO: Implement Microsoft Graph API call here
    return 0


# === Celery task ===
@shared_task
def sync_all_emails():
    """Sync emails for all active accounts"""
    try:
        active_accounts = EmailAccount.objects.filter(is_active=True)
        total_synced = 0

        for account in active_accounts:
            if account.provider == "gmail":
                total_synced += fetch_gmail_emails(account)
            elif account.provider == "outlook":
                total_synced += fetch_outlook_emails(account)

        logger.info(f"Batch sync completed: {total_synced} emails synced.")
        return {"status": "success", "total": total_synced}

    except Exception as e:
        logger.error(f"Error during batch sync: {str(e)}")
        return {"status": "error", "message": str(e)}



@shared_task
def analyze_email_importance_task(email_id):
    """
    Analyze email importance using AI
    Uses OpenAI to determine email importance based on content
    """
    try:
        email = Email.objects.get(id=email_id)
        
        # Use OpenAI to analyze importance
        if settings.OPENAI_API_KEY:
            openai.api_key = settings.OPENAI_API_KEY
            
            prompt = f"""
            Analyze the importance of this email and rate it from 0 to 1.
            
            Subject: {email.subject}
            Sender: {email.sender}
            Body: {email.body[:500]}
            
            Consider factors like:
            - Urgency indicators
            - Sender importance
            - Content relevance
            - Action required
            
            Provide a score (0-1) and brief explanation.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an email importance analyzer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200
            )
            
            analysis = response.choices[0].message.content
            
            # Parse score from response (simplified)
            score = 0.5  # Default
            if 'critical' in analysis.lower() or 'urgent' in analysis.lower():
                score = 0.9
                importance = 'critical'
            elif 'high' in analysis.lower():
                score = 0.75
                importance = 'high'
            elif 'low' in analysis.lower():
                score = 0.25
                importance = 'low'
            else:
                score = 0.5
                importance = 'medium'
            
            email.importance_score = score
            email.importance = importance
            email.importance_analysis = analysis
            email.analyzed_at = timezone.now()
            email.save()
            
            return {'status': 'success', 'email_id': email_id, 'importance': importance}
        else:
            logger.warning('OpenAI API key not configured')
            return {'status': 'error', 'message': 'OpenAI API key not configured'}
            
    except Email.DoesNotExist:
        logger.error(f'Email {email_id} not found')
        return {'status': 'error', 'message': 'Email not found'}
    except Exception as e:
        logger.error(f'Error analyzing email importance: {str(e)}')
        return {'status': 'error', 'message': str(e)}


@shared_task
def analyze_email_importance():
    """Analyze importance for unanalyzed emails"""
    try:
        unanalyzed_emails = Email.objects.filter(analyzed_at__isnull=True)[:50]
        for email in unanalyzed_emails:
            analyze_email_importance_task.delay(email.id)
        return {'status': 'success', 'count': unanalyzed_emails.count()}
    except Exception as e:
        logger.error(f'Error in batch importance analysis: {str(e)}')
        return {'status': 'error', 'message': str(e)}
