# from celery import shared_task
# from django.conf import settings
# from django.utils import timezone
# import openai
# import logging
# from .models import EmailAccount, Email
# import base64
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build
# from django.contrib.auth import get_user_model
# from .utils import fetch_gmail_emails

# User = get_user_model()




# logger = logging.getLogger(__name__)


# @shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
# def sync_email_account(self, account_id):
#     """
#     Sync emails from Gmail or Outlook using stored tokens.
#     """
#     email_count = 100
#     try:
#         account = EmailAccount.objects.get(id=account_id)
#         provider = account.provider.lower()

#         if provider == "gmail":
#             logger.info(f"Syncing Gmail account {account.email_address}")
#             count = fetch_gmail_emails(account, email_count=email_count)
#             return {"status": "success", "count": count}

#         elif provider == "outlook":
#             logger.info(f"Syncing Outlook account {account.email_address}")
#             # TODO: implement Outlook equivalent later
#             return {"status": "success", "message": "Outlook sync not yet implemented"}

#     except Exception as e:
#         logger.error(f"Error syncing {account.provider} for user {account.user.id}: {str(e)}")
#         return {"status": "error", "message": str(e)}





# # === Placeholder for Outlook ===
# def exchange_outlook_auth_code(auth_code):
#     # TODO: Implement Microsoft Graph token exchange here
#     return {"access_token": "OUTLOOK_ACCESS", "refresh_token": "OUTLOOK_REFRESH"}


# def fetch_outlook_emails(account):
#     # TODO: Implement Microsoft Graph API call here
#     return 0


# # === Celery task ===
# @shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
# def sync_all_emails(self):
#     """Sync emails for all active accounts"""
#     try:
#         active_accounts = EmailAccount.objects.filter(is_active=True)
#         total_synced = 0

#         for account in active_accounts:
#             print("account", account.provider, account.email_address)
#             if account.provider == "gmail":
#                 total_synced += 1
#                 sync_email_account.delay(account.id)
#             elif account.provider == "outlook":
#                 total_synced += fetch_outlook_emails(account)

#         logger.info(f"Batch sync completed: {total_synced} emails synced.")
#         return {"status": "success", "total": total_synced}

#     except Exception as e:
#         logger.error(f"Error during batch sync: {str(e)}")
#         return {"status": "error", "message": str(e)}



# @shared_task
# def analyze_email_importance_task(email_id):
#     """
#     Analyze email importance using AI
#     Uses OpenAI to determine email importance based on content
#     """
#     try:
#         email = Email.objects.get(id=email_id)
        
#         # Use OpenAI to analyze importance
#         if settings.OPENAI_API_KEY:
#             openai.api_key = settings.OPENAI_API_KEY
            
#             prompt = f"""
#             Analyze the importance of this email and rate it from 0 to 1.
            
#             Subject: {email.subject}
#             Sender: {email.sender}
#             Body: {email.body[:500]}
            
#             Consider factors like:
#             - Urgency indicators
#             - Sender importance
#             - Content relevance
#             - Action required
            
#             Provide a score (0-1) and brief explanation.
#             """
            
#             response = openai.ChatCompletion.create(
#                 model="gpt-3.5-turbo",
#                 messages=[
#                     {"role": "system", "content": "You are an email importance analyzer."},
#                     {"role": "user", "content": prompt}
#                 ],
#                 max_tokens=200
#             )
            
#             analysis = response.choices[0].message.content
            
#             # Parse score from response (simplified)
#             score = 0.5  # Default
#             if 'critical' in analysis.lower() or 'urgent' in analysis.lower():
#                 score = 0.9
#                 importance = 'critical'
#             elif 'high' in analysis.lower():
#                 score = 0.75
#                 importance = 'high'
#             elif 'low' in analysis.lower():
#                 score = 0.25
#                 importance = 'low'
#             else:
#                 score = 0.5
#                 importance = 'medium'
            
#             email.importance_score = score
#             email.importance = importance
#             email.importance_analysis = analysis
#             email.analyzed_at = timezone.now()
#             email.save()
            
#             return {'status': 'success', 'email_id': email_id, 'importance': importance}
#         else:
#             logger.warning('OpenAI API key not configured')
#             return {'status': 'error', 'message': 'OpenAI API key not configured'}
            
#     except Email.DoesNotExist:
#         logger.error(f'Email {email_id} not found')
#         return {'status': 'error', 'message': 'Email not found'}
#     except Exception as e:
#         logger.error(f'Error analyzing email importance: {str(e)}')
#         return {'status': 'error', 'message': str(e)}


# @shared_task
# def analyze_email_importance():
#     """Analyze importance for unanalyzed emails"""
#     try:
#         unanalyzed_emails = Email.objects.filter(analyzed_at__isnull=True)[:50]
#         for email in unanalyzed_emails:
#             analyze_email_importance_task.delay(email.id)
#         return {'status': 'success', 'count': unanalyzed_emails.count()}
#     except Exception as e:
#         logger.error(f'Error in batch importance analysis: {str(e)}')
#         return {'status': 'error', 'message': str(e)}




# @shared_task
# def periodic_email_sync():
#     """Periodically syncs Gmail inboxes for connected users."""
#     logger.info("Starting periodic email sync...")
#     try:
#         synced = sync_all_emails.delay()
#         logger.info(f"✅ Synced {len(synced)} emails")
#     except Exception as e:
#         logger.error(f"❌ Failed syncing emails: {e}")

#     logger.info("Finished periodic email sync.")

