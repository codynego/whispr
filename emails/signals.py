# emails/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Email
from .utils import is_email_important
from whisprai.ai.gemini_client import get_gemini_response
from whatsapp.models import WhatsAppMessage
from whatsapp.tasks import send_whatsapp_message_task
from django.conf import settings

@receiver(post_save, sender=Email)
def generate_email_embedding_and_importance(sender, instance, created, **kwargs):
    if created and not instance.embedding_generated:
        # Combine subject + body for better representation
        user = instance.account.user
        sender_number = user.whatsapp if hasattr(user, 'whatsapp') else None
        text = f"{instance.subject}\n\n{instance.body}\n\n{instance.sender_name}\n\n{instance.received_at}".strip()
        if not text:
            return  # skip empty emails

        # Compute embedding and importance
        email_embedding, is_important, combined_score = is_email_important(text)

        # Determine importance level from score
        if combined_score >= 0.9:
            importance_level = "critical"
        elif combined_score >= 0.75:
            importance_level = "high"
        elif combined_score >= 0.55:
            importance_level = "medium"
        else:
            importance_level = "low"

        # Build human-readable analysis summary
        analysis_text = (
            f"Importance score: {combined_score:.2f} — "
            f"Marked as {importance_level.upper()} "
            f"({'important' if is_important else 'normal'})"
        )

        if importance_level in ["high", "critical"]:
            analysis_text += " — Requires prompt attention."
            report = get_gemini_response(instance.body, user_id=user.id, task_type="report")
            response_message = WhatsAppMessage.objects.create(
                user=user,
                to_number=sender_number,
                message=report,
                alert_type='importance_alert'
            )
            # Optionally, send WhatsApp alert about important email
            send_whatsapp_message_task.delay(to_number=sender_number, message=f"⚠️ Important Email Alert\n\n{report}")
            

        # Save updates
        instance.embedding = email_embedding.tolist() if email_embedding is not None else None
        instance.importance = importance_level
        instance.importance_score = combined_score
        instance.importance_analysis = analysis_text
        instance.analyzed_at = timezone.now()
        instance.embedding_generated = True
        instance.save(update_fields=[
            "embedding", "importance", "importance_score",
            "importance_analysis", "analyzed_at", "embedding_generated"
        ])
