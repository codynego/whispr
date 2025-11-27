# whisone/avatars/training.py
from .models import Avatar, AvatarSource, AvatarMemoryChunk, AvatarTrainingJob
from django.utils import timezone



def train_avatar(avatar: Avatar, job: AvatarTrainingJob):
    """
    Processes all enabled sources for the Avatar and updates memory chunks & persona.
    """
    job.status = "running"
    job.started_at = timezone.now()
    job.save()

    all_texts = []

    try:
        sources = AvatarSource.objects.filter(avatar=avatar, enabled=True)

        for source in sources:

            # ---------------------
            # Notes
            # ---------------------
            if source.source_type == "notes" and source.include_for_knowledge:
                note_ids = source.metadata.get("note_ids", [])
                from whisone.models import Note
                notes = Note.objects.filter(id__in=note_ids, owner=avatar.owner)
                for note in notes:
                    text = note.content.strip()
                    all_texts.append(text)
                    AvatarMemoryChunk.objects.create(
                        avatar=avatar,
                        text=text,
                        source_type="notes"
                    )

            # ---------------------
            # File Uploads
            # ---------------------
            elif source.source_type == "uploads" and source.include_for_knowledge:
                file_ids = source.metadata.get("file_ids", [])
                from whisone.models import UploadedFile
                files = UploadedFile.objects.filter(id__in=file_ids, owner=avatar.owner)
                for f in files:
                    text = f.extract_text()  # implement extract_text in your model
                    all_texts.append(text)
                    AvatarMemoryChunk.objects.create(
                        avatar=avatar,
                        text=text,
                        source_type="uploads"
                    )

            # ---------------------
            # Manual Q&A / Tone
            # ---------------------
            elif source.source_type == "manual" and source.include_for_tone:
                qa_list = source.metadata.get("qa_pairs", [])
                for qa in qa_list:
                    text = f"Q: {qa.get('question')}\nA: {qa.get('answer')}"
                    all_texts.append(text)
                    AvatarMemoryChunk.objects.create(
                        avatar=avatar,
                        text=text,
                        source_type="manual"
                    )

            # ---------------------
            # WhatsApp
            # ---------------------
            elif source.source_type == "whatsapp" and source.include_for_knowledge:
                chat_ids = source.metadata.get("chat_ids", [])
                from whatsapp.models import WhatsAppMessage
                messages = WhatsAppMessage.objects.filter(id__in=chat_ids, owner=avatar.owner)
                for msg in messages:
                    text = msg.content.strip()
                    all_texts.append(text)
                    AvatarMemoryChunk.objects.create(
                        avatar=avatar,
                        text=text,
                        source_type="whatsapp"
                    )

        # ---------------------
        # Update persona / knowledge
        # ---------------------
        avatar.persona_prompt = f"Avatar {avatar.name}'s persona based on {len(all_texts)} sources."
        avatar.summary_knowledge = f"{len(all_texts)} text chunks loaded for knowledge."
        avatar.trained = True
        avatar.trained_at = timezone.now()
        avatar.save()

        # ---------------------
        # Complete job
        # ---------------------
        job.status = "completed"
        job.finished_at = timezone.now()
        job.add_log(f"Training completed: {len(all_texts)} chunks processed.")

    except Exception as e:
        job.status = "error"
        job.finished_at = timezone.now()
        job.add_log(f"Error during training: {str(e)}")
        avatar.trained = False
        avatar.save()
