# emails/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Email
from whisprai.ai.embeddings import get_text_embedding

@receiver(post_save, sender=Email)
def generate_email_embedding(sender, instance, created, **kwargs):
    if created and not instance.embedding:
        text = f"{instance.subject}\n\n{instance.body}"
        embedding = get_text_embedding(text)
        if embedding:
            instance.embedding = embedding
            instance.save(update_fields=["embedding"])
