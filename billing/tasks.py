from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging
from .models import Subscription, Payment

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task
def process_successful_payment(payment_id):
    """
    Process a successful payment and update subscription
    """
    try:
        payment = Payment.objects.get(id=payment_id)
        
        # Update payment status
        payment.status = 'success'
        payment.paid_at = timezone.now()
        payment.save()
        
        # Update user subscription
        user = payment.user
        subscription, created = Subscription.objects.get_or_create(user=user)
        
        if payment.plan:
            subscription.plan = payment.plan
            subscription.status = 'active'
            subscription.amount = payment.amount
            subscription.currency = payment.currency
            
            # Set subscription end date (30 days from now)
            from datetime import timedelta
            subscription.end_date = timezone.now() + timedelta(days=30)
            subscription.next_payment_date = subscription.end_date
            subscription.save()
            
            # Update user plan
            user.plan = payment.plan
            user.save()
            
            logger.info(f'Subscription updated for user {user.id} to {payment.plan}')
        
        return {'status': 'success', 'payment_id': payment_id}
        
    except Payment.DoesNotExist:
        logger.error(f'Payment {payment_id} not found')
        return {'status': 'error', 'message': 'Payment not found'}
    except Exception as e:
        logger.error(f'Error processing payment {payment_id}: {str(e)}')
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_expired_subscriptions():
    """
    Check and update expired subscriptions
    """
    try:
        from datetime import datetime
        now = timezone.now()
        
        expired_subscriptions = Subscription.objects.filter(
            status='active',
            end_date__lte=now
        )
        
        count = 0
        for subscription in expired_subscriptions:
            subscription.status = 'expired'
            subscription.save()
            
            # Downgrade user to free plan
            user = subscription.user
            user.plan = 'free'
            user.save()
            
            count += 1
            logger.info(f'Subscription expired for user {user.id}')
        
        return {'status': 'success', 'count': count}
        
    except Exception as e:
        logger.error(f'Error checking expired subscriptions: {str(e)}')
        return {'status': 'error', 'message': str(e)}
