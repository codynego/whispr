# channels/tasks.py
from celery import shared_task
from .models import ChannelAccount  # this replaces EmailAccount later
from .registry import CHANNEL_SYNC_HANDLERS
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3)
def sync_channel_account(self, account_id):
    """
    Unified sync task for all connected channels (email, slack, whatsapp, etc.).
    """
    try:
        account = ChannelAccount.objects.get(id=account_id)
        channel = account.provider.lower()

        handler = CHANNEL_SYNC_HANDLERS.get(channel)
        if not handler:
            logger.warning(f"No sync handler defined for {channel}")
            return {"status": "skipped", "message": f"No handler for {channel}"}

        logger.info(f"Syncing {channel} account {account.display_name or account.email_address}")
        count = handler(account)

        return {"status": "success", "count": count}

    except ChannelAccount.DoesNotExist:
        return {"status": "error", "message": f"Account {account_id} not found"}

    except Exception as e:
        logger.error(f"Error syncing {channel} for user {account.user.id}: {str(e)}")
        return {"status": "error", "message": str(e)}
