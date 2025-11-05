from celery import shared_task
from django.utils import timezone
from django.conf import settings
import logging
from django.contrib.auth import get_user_model

from unified.models import ChannelAccount, Message, Conversation
from unified.utils.email_util import (
    fetch_gmail_messages
)

User = get_user_model()
logger = logging.getLogger(__name__)

# ==============================================================
# === Generic Unified Sync Task
# ==============================================================

@shared_task(
    bind=True,
    soft_time_limit=600,   # 10 min soft
    time_limit=660,       # 11 min hard
    autoretry_for=(Exception,),
    max_retries=3
)
def sync_channel_account(self, account_id: int):
    """
    Generic task to sync messages for any connected channel (email, WhatsApp, Slack, etc.).
    Uses provider to route to correct fetch function.
    """
    try:
        account = ChannelAccount.objects.get(id=account_id, is_active=True)
        provider = account.provider.lower()
        channel = account.channel.lower()

        logger.info(f"🔄 Syncing {provider} ({channel}) for {account.user.email}")

        if channel == "email":
            if provider == "gmail":
                count = fetch_gmail_messages(account.id, limit=10)
            elif provider == "outlook":
                count = fetch_gmail_messages(account.id, limit=10)
            else:
                logger.warning(f"⚠️ Unsupported email provider: {provider}")
                return {"status": "error", "message": f"Unsupported provider {provider}"}

        # elif channel == "whatsapp":
        #     count = fetch_whatsapp_messages(account)

        # elif channel == "slack":
        #     count = fetch_slack_messages(account)

        else:
            logger.warning(f"⚠️ Unsupported channel: {channel}")
            return {"status": "error", "message": f"Unsupported channel {channel}"}

        account.last_synced = timezone.now()
        account.save(update_fields=["last_synced"])

        logger.info(f"✅ Synced {count} messages for {account.address_or_id}")
        return {"status": "success", "count": count}

    except ChannelAccount.DoesNotExist:
        return {"status": "error", "message": f"Account {account_id} not found"}
    except Exception as e:
        logger.error(f"❌ Error syncing channel account {account_id}: {e}")
        return {"status": "error", "message": str(e)}

# ==============================================================
# === Batch Sync All Accounts
# ==============================================================


def sync_all_channel_accounts():
    """Sync messages for all active channel accounts (email, WhatsApp, Slack, etc.)."""
    try:
        active_accounts = ChannelAccount.objects.filter(is_active=True)
        total_synced = 0

        for account in active_accounts:
            sync_channel_account.delay(account.id)
            total_synced += 1

        logger.info(f"Batch sync started for {total_synced} accounts.")
        return {"status": "success", "total_accounts": total_synced}

    except Exception as e:
        logger.error(f"Error during batch sync: {str(e)}")
        return {"status": "error", "message": str(e)}

# ==============================================================
# === Email-Specific Tasks (still works seamlessly)
# ==============================================================

@shared_task
def analyze_message_importance():
    """Analyze importance for unanalyzed messages (emails or others)."""
    from unified.ai import analyze_message_importance_task

    try:
        unanalyzed = Message.objects.filter(analyzed_at__isnull=True)[:50]
        for msg in unanalyzed:
            analyze_message_importance_task.delay(msg.id)
        return {'status': 'success', 'count': unanalyzed.count()}
    except Exception as e:
        logger.error(f'Error in batch importance analysis: {str(e)}')
        return {'status': 'error', 'message': str(e)}


# ==============================================================
# === Periodic Scheduled Sync
# ==============================================================

@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
def periodic_channel_sync(self):
    """Periodically syncs all connected accounts."""
    logger.info("⏰ Starting periodic unified channel sync...")
    try:
        sync_all_channel_accounts()
    except Exception as e:
        logger.error(f"❌ Failed periodic sync: {e}")
    logger.info("✅ Finished periodic unified channel sync.")
