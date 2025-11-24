# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.utils import timezone
# from unified.models import Message
# from unified.utils.common_utils import is_message_important, get_embedding
# from whatsapp.models import WhatsAppMessage
# from whatsapp.tasks import send_whatsapp_message_task


# from celery import shared_task
# from unified.models import Message
# from whisprai.ai.gemini_client import get_ai_response
# from django.utils import timezone
# import json
# import re
# from assistant.models import Automation
# from assistant.tasks import execute_automation

# @shared_task
# def analyze_message_insights(message_id):
#     """
#     Runs Gemini AI insights for a Message and saves the results.
#     """
#     try:
#         message = Message.objects.get(id=message_id)
#         user = message.account.user

#         subject = getattr(message, "subject", "") or message.metadata.get("subject", "")
#         body = getattr(message, "content", "") or message.metadata.get("body", "")
#         sender_name = getattr(message, "sender_name", "") or message.metadata.get("from", "")
#         text_parts = [subject, body, sender_name]
#         text = "\n\n".join([t for t in text_parts if t]).strip()
#         if not text:
#             print(f"⚠️ No text found for message {message_id}")
#             return

#         print(f"🔍 Running Gemini insights for message {message_id}...")

#         # Call Gemini
#         response = get_ai_response(prompt=text, task_type="insights", user_id=user.id)

#         # Extract the JSON block inside ```json ... ```
#         raw_text = response.get("raw", "")
#         match = re.search(r"```json(.*?)```", raw_text, re.S)
#         if match:
#             clean_json = match.group(1).strip()
#             insights = json.loads(clean_json)
#         else:
#             insights = json.loads(raw_text) if raw_text.strip().startswith("{") else {}

#         print(f"✅ Gemini insights received for message {message_id}: {insights}")

#         # Parse structured insights
#         ai_summary = insights.get("summary")
#         ai_next_step = insights.get("next_step")
#         ai_people = insights.get("people", [])
#         ai_organizations = insights.get("organizations", [])
#         ai_related = insights.get("related_topics", [])

#         # Save results
#         message.ai_summary = ai_summary
#         message.ai_next_step = ai_next_step
#         message.ai_people = ai_people
#         message.ai_organizations = ai_organizations
#         message.ai_related = ai_related
#         message.analyzed_at = timezone.now()
#         message.importance = insights.get("importance_level", message.importance)
#         message.importance_score = insights.get("importance_score", message.importance_score)
#         message.embedding = insights.get("embedding", message.embedding)
#         message.label = insights.get("label", message.label)
        
#         message.save(update_fields=[
#             "ai_summary",
#             "ai_next_step",
#             "ai_people",
#             "ai_organizations",
#             "ai_related",
#             "analyzed_at",
#             "importance",
#             "importance_score",
#             "embedding",
#             "label"
#         ])

#         print(f"✅ Gemini insights saved for message {message_id}")

#     except Exception as e:
#         print(f"❌ analyze_message_insights failed for {message_id}: {e}")


# @receiver(post_save, sender=Message)
# def handle_new_message(sender, instance, created, **kwargs):
#     """
#     When a new Message is created:
#     - Compute importance and embedding
#     - Queue Gemini AI insight generation (async)
#     - Optionally send WhatsApp alert if important
#     """
#     if not created or instance.embedding_generated:
#         return

#     user = instance.account.user
#     sender_number = getattr(user, "whatsapp", None)
#     analyze_message_insights.delay(instance.id)

#     # Gather text content
#     subject = getattr(instance, "subject", "") or instance.metadata.get("subject", "")
#     body = getattr(instance, "content", "") or instance.metadata.get("body", "")
#     sender_name = getattr(instance, "sender_name", "") or instance.metadata.get("from", "")

#     text_parts = [subject, body, sender_name]
#     text = "\n\n".join([t for t in text_parts if t]).strip()
#     if not text:
#         return

#     # === Compute importance ===
#     # message_embedding, is_important, combined_score = is_message_important(text)

#     if instance.importance_score >= 0.9:
#         instance.importance = "critical"
#     elif instance.importance_score >= 0.75:
#         instance.importance = "high"
#     elif instance.importance_score >= 0.55:
#         instance.importance = "medium"
#     else:
#         instance.importance = "low"

#     # analysis_text = (
#     #     f"Importance score: {combined_score:.2f} — "
#     #     f"Marked as {importance_level.upper()} "
#     #     f"({'important' if is_important else 'normal'})"
#     # )

#     # === Update the instance immediately ===
#     # instance.embedding = message_embedding.tolist() if message_embedding is not None else None
#     # instance.importance = importance_level
#     # instance.importance_score = combined_score
#     # # instance.importance_analysis = analysis_text
#     instance.analyzed_at = timezone.now()
#     instance.embedding_generated = True
#     instance.save(update_fields=[
#         "importance",
#         "importance_score",
#         "analyzed_at",
#         "embedding_generated",
#     ])

#     # === Queue Gemini AI analysis ===
    

#     # === Optional: send WhatsApp alert ===
#     if instance.importance in ["high", "critical"] and sender_number:
#         alert_message = f"*Important Message:*\n{instance.subject}"
#         try:
#             response_message = WhatsAppMessage.objects.create(
#                 user=user,
#                 to_number=sender_number,
#                 message=alert_message,
#                 alert_type="importance_alert"
#             )
#             send_whatsapp_message_task.delay(message_id=response_message.id)
#         except Exception as e:
#             print(f"⚠️ WhatsApp alert failed: {e}")





# # @receiver(post_save, sender=Message)
# # def trigger_automations_on_new_message(sender, instance, created, **kwargs):
# #     if not created:
# #         return  # Only run for new messages

# #     # Filter automations for this user that listen to "on_new_message"
# #     automations = Automation.objects.filter(
# #         user=instance.account.user,
# #         trigger_type="on_email_received",
# #         is_active=True,
# #     )

# #     for automation in automations:
# #         execute_automation.delay(automation.id)


# import json
# import re
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from unified.models import Message
# from assistant.models import Automation  # Adjust to your app
# from assistant.tasks import execute_automation  # Your Celery task

# @receiver(post_save, sender=Message)
# def trigger_automations_on_new_message(sender, instance, created, **kwargs):
#     if not created:
#         return  # Only for new messages

#     # Helper to extract subject (from metadata or content fallback)
#     def get_subject(msg):
#         metadata = msg.metadata or {}
#         subject = metadata.get("subject") or msg.content[:100].split('\n')[0].strip() if msg.content else "No Subject"
#         return subject

#     # Helper for basic keywords (simple extraction; enhance with NLP if needed)
#     def extract_keywords(text, max_keywords=5):
#         if not text:
#             return []
#         words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
#         common = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was", "one", "our", "out", "day", "get", "has", "him", "his", "how", "man", "new", "now", "old", "see", "two", "way", "who", "boy", "did", "its", "let", "put", "say", "she", "too", "use"}
#         keywords = [w for w in words if w not in common and len(w) > 3]
#         return list(set(keywords))[:max_keywords]  # Dedupe and limit

#     # Build rich context from the model
#     context = {
#         "channel": instance.channel,
#         "sender": instance.sender,
#         "sender_name": instance.sender_name,
#         "recipients": instance.recipients,  # List from JSON
#         "subject": get_subject(instance),
#         "text": instance.content,  # Decrypted content
#         "keywords": extract_keywords(instance.content),
#         "attachments": instance.attachments,  # List of dicts
#         "importance": instance.importance,
#         "importance_score": instance.importance_score,
#         "ai_summary": instance.ai_summary if instance.analyzed_at else None,  # Only if analyzed
#         "ai_next_step": instance.ai_next_step if instance.analyzed_at else None,
#         "ai_people": instance.ai_people,
#         "ai_organizations": instance.ai_organizations,
#         "conversation_id": instance.conversation.id,
#         "external_id": instance.external_id,
#         "sent_at": instance.sent_at.isoformat() if instance.sent_at else None,
#         "message_id": instance.id,
#     }

#     # Filter automations: Use "on_message_received" for generality, with channel in conditions
#     automations = Automation.objects.filter(
#         user=instance.account.user,  # Links to user via ChannelAccount
#         trigger_type="on_message_received",  # Or keep "on_email_received" if channel-specific
#         is_active=True,
#     ).select_related("user")

#     for automation in automations:
#         # Optional: Pre-filter by channel in trigger_condition
#         cond = automation.trigger_condition or {}
#         if cond.get("channel") and cond["channel"] != instance.channel:
#             continue

#         # Queue with context
#         execute_automation.delay(automation.id, json.dumps(context))