# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import User
from whisone.marketing.whatsapp_sequence import trigger_welcome


@receiver(post_save, sender=User)
def send_welcome_on_signup(sender, instance, created, **kwargs):
    """
    Sends the Day-0 welcome message as soon as a new user is created.
    """
    if created:
        # Trigger asynchronous welcome message
        trigger_welcome(instance.id)
