from celery import shared_task
from django.conf import settings
from django.utils import timezone
import openai
import logging
from .models import EmailAccount, Email

logger = logging.getLogger(__name__)


@shared_task
def sync_email_account(user_id, provider, authorization_code):
    """
    Sync emails from Gmail or Outlook
    This is a placeholder - implement actual OAuth flow and API calls
    """
    try:
        # TODO: Implement actual Gmail/Outlook API integration
        # 1. Exchange authorization code for tokens
        # 2. Store tokens in EmailAccount
        # 3. Fetch emails using provider API
        # 4. Store emails in Email model
        
        logger.info(f'Syncing emails for user {user_id} from {provider}')
        return {'status': 'success', 'message': 'Email sync completed'}
    except Exception as e:
        logger.error(f'Error syncing emails: {str(e)}')
        return {'status': 'error', 'message': str(e)}


@shared_task
def sync_all_emails():
    """Sync emails for all active email accounts"""
    try:
        active_accounts = EmailAccount.objects.filter(is_active=True)
        for account in active_accounts:
            # TODO: Implement actual sync logic
            logger.info(f'Syncing account {account.email_address}')
        return {'status': 'success', 'count': active_accounts.count()}
    except Exception as e:
        logger.error(f'Error in batch sync: {str(e)}')
        return {'status': 'error', 'message': str(e)}


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
