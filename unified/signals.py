from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from unified.models import Message
from unified.utils.common_utils import is_message_important
from whatsapp.models import WhatsAppMessage
from whatsapp.tasks import send_whatsapp_message_task

from celery import shared_task, chain
from unified.models import Message
from whisprai.ai.gemini_client import get_gemini_response
from django.utils import timezone
import json
import re
import traceback  # For better logging

@shared_task
def compute_message_importance_and_alert(message_id):
    """
    Async: Computes importance/embedding, updates Message, sends WhatsApp alert if needed.
    Runs after post_save signal queues it.
    """
    try:
        message = Message.objects.select_related('account__user').get(id=message_id)
        if message.embedding_generated:
            print(f"⚠️ Message {message_id} already processed, skipping")
            return

        user = message.account.user
        sender_number = getattr(user, "whatsapp", None)

        # Gather text content (same as before)
        subject = getattr(message, "subject", "") or message.metadata.get("subject", "")
        body = getattr(message, "content", "") or message.metadata.get("body", "")
        sender_name = getattr(message, "sender_name", "") or message.metadata.get("from", "")
        text_parts = [subject, body, sender_name]
        text = "\n\n".join([t for t in text_parts if t]).strip()
        if not text:
            print(f"⚠️ No text for message {message_id}, skipping")
            return

        print(f"🔍 Computing importance for message {message_id}...")

        # Compute importance (now async)
        message_embedding, is_important, combined_score = is_message_important(text)

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

        # Update in one atomic block
        with transaction.atomic():
            message.embedding = message_embedding.tolist() if message_embedding is not None else None
            message.importance = importance_level
            message.importance_score = combined_score
            message.importance_analysis = analysis_text
            message.analyzed_at = timezone.now()
            message.embedding_generated = True
            message.save(update_fields=[
                "embedding",
                "importance",
                "importance_score",
                "importance_analysis",
                "analyzed_at",
                "embedding_generated",
            ])

        print(f"✅ Importance computed & saved for message {message_id}")

        # Queue Gemini AI analysis (unchanged)
        analyze_message_insights.delay(message.id)

        # === Async WhatsApp alert ===
        if importance_level in ["medium", "high", "critical"] and sender_number:
            alert_message = f"{analysis_text}\n\n📄 *Summary:* Pending analysis...\n💡 *Next Step:* Pending analysis..."
            try:
                response_message = WhatsAppMessage.objects.create(
                    user=user,
                    to_number=sender_number,
                    message=alert_message,
                    alert_type="importance_alert"
                )
                send_whatsapp_message_task.delay(message_id=response_message.id)
                print(f"📱 Queued WhatsApp alert for {message_id}")
            except Exception as e:
                print(f"⚠️ WhatsApp alert creation failed for {message_id}: {e}")

    except Exception as e:
        print(f"❌ compute_message_importance_and_alert failed for {message_id}: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        # Optionally retry: self.retry(countdown=60, exc=e)


@shared_task
def analyze_message_insights(message_id):
    """
    Runs Gemini AI insights for a Message and saves the results.
    (Unchanged, but added traceback for robustness)
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
        print(f"Full traceback: {traceback.format_exc()}")


@receiver(post_save, sender=Message)
def handle_new_message(sender, instance, created, **kwargs):
    """
    Lightweight signal: Just queue async processing if new.
    """
    if not created or instance.embedding_generated:
        return

    # Quick text check (minimal DB—no fetches)
    text_parts = []
    if hasattr(instance, 'subject') and instance.subject:
        text_parts.append(instance.subject)
    if hasattr(instance, 'content') and instance.content:
        text_parts.append(instance.content)
    if hasattr(instance, 'sender_name') and instance.sender_name:
        text_parts.append(instance.sender_name)
    if hasattr(instance, 'metadata'):
        text_parts.append(instance.metadata.get("subject", ""))
        text_parts.append(instance.metadata.get("body", ""))
        text_parts.append(instance.metadata.get("from", ""))
    text = "\n\n".join([t for t in text_parts if t]).strip()
    if not text:
        return

    try:
        # Queue the heavy lifting
        compute_message_importance_and_alert.delay(instance.id)
        print(f"📝 Queued importance/alert for new message {instance.id}")
    except Exception as e:
        print(f"⚠️ Failed to queue importance task for {instance.id}: {e}")