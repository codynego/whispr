from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from unified.models import Message
from unified.utils.common_utils import is_message_important
from whatsapp.models import WhatsAppMessage
from whatsapp.tasks import send_whatsapp_message_task


from celery import shared_task
from unified.models import Message
from whisprai.ai.gemini_client import get_gemini_response
from django.utils import timezone
import json
import re

@shared_task
def analyze_message_insights(message_id):
    """
    Runs Gemini AI insights for a Message and saves the results.
    """
    try:
        message = Message.objects.get(id=message_id)
        user = message.account.user

        subject = getattr(message, "subject", "") or message.metadata.get("subject", "")
        body = getattr(message, "content", "") or message.metadata.get("body", "")
        sender_name = getattr(message, "sender_name", "") or message.metadata.get("from", "")
        text_parts = [subject, body, sender_name]
        text = "\n\n".join([t for t in text_parts if t]).strip()
        if not text:
            print(f"⚠️ No text found for message {message_id}")
            return

        print(f"🔍 Running Gemini insights for message {message_id}...")

        # Call Gemini
        response = get_gemini_response(prompt=text, task_type="insights", user_id=user.id)

        # Extract the JSON block inside ```json ... ```
        raw_text = response.get("raw", "")
        match = re.search(r"```json(.*?)```", raw_text, re.S)
        if match:
            clean_json = match.group(1).strip()
            insights = json.loads(clean_json)
        else:
            insights = json.loads(raw_text) if raw_text.strip().startswith("{") else {}

        print(f"✅ Gemini insights received for message {message_id}: {insights}")

        # Parse structured insights
        ai_summary = insights.get("summary")
        ai_next_step = insights.get("next_step")
        ai_people = insights.get("people", [])
        ai_organizations = insights.get("organizations", [])
        ai_related = insights.get("related_topics", [])

        # Save results
        message.ai_summary = ai_summary
        message.ai_next_step = ai_next_step
        message.ai_people = ai_people
        message.ai_organizations = ai_organizations
        message.ai_related = ai_related
        message.analyzed_at = timezone.now()
        message.importance = insights.get("importance_level", message.importance)
        message.importance_score = insights.get("importance_score", message.importance_score)
        message.save(update_fields=[
            "ai_summary",
            "ai_next_step",
            "ai_people",
            "ai_organizations",
            "ai_related",
            "analyzed_at",
        ])

        print(f"✅ Gemini insights saved for message {message_id}")

    except Exception as e:
        print(f"❌ analyze_message_insights failed for {message_id}: {e}")


@receiver(post_save, sender=Message)
def handle_new_message(sender, instance, created, **kwargs):
    """
    When a new Message is created:
    - Compute importance and embedding
    - Queue Gemini AI insight generation (async)
    - Optionally send WhatsApp alert if important
    """
    if not created or instance.embedding_generated:
        return

    user = instance.account.user
    sender_number = getattr(user, "whatsapp", None)
    analyze_message_insights.delay(instance.id)

    # Gather text content
    subject = getattr(instance, "subject", "") or instance.metadata.get("subject", "")
    body = getattr(instance, "content", "") or instance.metadata.get("body", "")
    sender_name = getattr(instance, "sender_name", "") or instance.metadata.get("from", "")

    text_parts = [subject, body, sender_name]
    text = "\n\n".join([t for t in text_parts if t]).strip()
    if not text:
        return

    # === Compute importance ===
    # message_embedding, is_important, combined_score = is_message_important(text)

    # if combined_score >= 0.9:
    #     importance_level = "critical"
    # elif combined_score >= 0.75:
    #     importance_level = "high"
    # elif combined_score >= 0.55:
    #     importance_level = "medium"
    # else:
    #     importance_level = "low"

    analysis_text = (
        f"Importance score: {combined_score:.2f} — "
        f"Marked as {importance_level.upper()} "
        f"({'important' if is_important else 'normal'})"
    )

    # === Update the instance immediately ===
    instance.embedding = message_embedding.tolist() if message_embedding is not None else None
    # instance.importance = importance_level
    # instance.importance_score = combined_score
    # # instance.importance_analysis = analysis_text
    instance.analyzed_at = timezone.now()
    instance.embedding_generated = True
    instance.save(update_fields=[
        "embedding",
        "analyzed_at",
        "embedding_generated",
    ])

    # === Queue Gemini AI analysis ===
    

    # === Optional: send WhatsApp alert ===
    if instance.importance in ["medium", "high", "critical"] and sender_number:
        alert_message = f"*Summary:* Pending analysis...\n💡 *Next Step:* Pending analysis..."
        try:
            response_message = WhatsAppMessage.objects.create(
                user=user,
                to_number=sender_number,
                message=alert_message,
                alert_type="importance_alert"
            )
            send_whatsapp_message_task.delay(message_id=response_message.id)
        except Exception as e:
            print(f"⚠️ WhatsApp alert failed: {e}")
