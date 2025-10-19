# unified/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from unified.models import Message
from unified.utils.common_utils import is_email_important
from whisprai.ai.gemini_client import get_gemini_response
from whatsapp.models import WhatsAppMessage
from whatsapp.tasks import send_whatsapp_message_task

@receiver(post_save, sender=Message)
def generate_message_embedding_and_importance(sender, instance, created, **kwargs):
    """
    Runs when a new Message is created.
    - Generates importance embedding
    - Sends WhatsApp alert for important messages (if applicable)
    """
    # Skip non-email messages for now
    if not created or instance.channel != "email" or instance.embedding_generated:
        return

    user = instance.account.user
    sender_number = getattr(user, "whatsapp", None)

    text = f"{instance.subject or ''}\n\n{instance.content or ''}\n\n{instance.sender_name or ''}".strip()
    if not text:
        return  # Skip empty or system messages

    # === Compute importance & embedding ===
    email_embedding, is_important, combined_score = is_email_important(text)

    if combined_score >= 0.9:
        importance_level = "critical"
    elif combined_score >= 0.75:
        importance_level = "high"
    elif combined_score >= 0.55:
        importance_level = "medium"
    else:
        importance_level = "low"

    analysis_text = (
        f"Importance score: {combined_score:.2f} — "
        f"Marked as {importance_level.upper()} "
        f"({'important' if is_important else 'normal'})"
    )

    # === Optional: send WhatsApp alert ===
    if importance_level in ["medium", "high", "critical"] and sender_number:
        analysis_text += " — Requires prompt attention."

        try:
            report = get_gemini_response(instance.content, user_id=user.id, task_type="report")
            response_message = WhatsAppMessage.objects.create(
                user=user,
                to_number=sender_number,
                message=report,
                alert_type="importance_alert"
            )
            send_whatsapp_message_task.delay(message_id=response_message.id)
        except Exception as e:
            print(f"⚠️ WhatsApp alert failed: {e}")

    # === Save updates ===
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
