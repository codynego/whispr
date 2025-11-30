# whisone/avatars/training.py

from avatars.models import Avatar, AvatarSource, AvatarMemoryChunk, AvatarTrainingJob
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


def normalize_embeddings(value):
    """
    Ensures embeddings are always returned as:
        - None OR
        - List[ List[float] ]
    Handles:
        - None
        - Single embedding list
        - Already correct list-of-lists
    """
    if not value:
        return None

    # Single embedding => convert to list-of-list
    if isinstance(value, list) and value and isinstance(value[0], float):
        return [value]

    # Proper list-of-list
    if isinstance(value, list) and isinstance(value[0], list):
        return value

    # Unknown format
    return None



def train_avatar(avatar: Avatar, job: AvatarTrainingJob):
    """
    Processes all enabled sources for the Avatar and updates memory chunks & persona.
    Handles embeddings in all states (None / single list / list of lists).
    """

    logger.info(f"STARTING training job {job.id} for avatar @{avatar.handle}")

    job.status = "running"
    job.started_at = timezone.now()
    job.save()

    all_texts = []

    try:
        sources = AvatarSource.objects.filter(avatar=avatar, enabled=True)
        logger.info(f"Found {sources.count()} enabled sources.")

        with transaction.atomic():

            for source in sources:
                logger.info(
                    f"Processing source {source.id} "
                    f"[type={source.source_type}, "
                    f"knowledge={source.include_for_knowledge}, "
                    f"tone={source.include_for_tone}]"
                )

                # -------------------------
                # NOTES
                # -------------------------
                if source.source_type == "notes" and source.include_for_knowledge:

                    from whisone.models import Note

                    note_ids = source.metadata.get("note_ids", [])
                    notes = Note.objects.filter(id__in=note_ids, user=avatar.owner)
                    logger.debug(f"Notes: {notes.count()} found.")

                    for note in notes:
                        text = (note.content or "").strip()
                        if not text:
                            continue

                        all_texts.append(text)

                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="notes",
                            embedding=normalize_embeddings(note.embedding),
                        )

                # -------------------------
                # FILE UPLOADS
                # -------------------------
                elif source.source_type == "uploads" and source.include_for_knowledge:

                    from whisone.models import UploadedFile

                    file_ids = source.metadata.get("ids", [])
                    files = UploadedFile.objects.filter(id__in=file_ids, user=avatar.owner)
                    logger.debug(f"Uploads: {files.count()} files loaded.")

                    for f in files:
                        text = (f.content or "").strip()
                        if not text:
                            continue

                        all_texts.append(text)

                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="uploads",
                            embedding=normalize_embeddings(f.embedding),
                        )

                # -------------------------
                # MANUAL Q&A (tone)
                # -------------------------
                elif source.source_type == "manual" and source.include_for_tone:

                    qa_list = source.metadata.get("qa_pairs", [])
                    logger.debug(f"Manual Q&A: {len(qa_list)} pairs.")

                    for qa in qa_list:
                        q = qa.get("question", "").strip()
                        A = qa.get("answer", "").strip()
                        if not q and not A:
                            continue

                        text = f"Q: {q}\nA: {A}"
                        all_texts.append(text)

                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="manual",
                            embedding=None,
                        )

                # -------------------------
                # WHATSAPP
                # -------------------------
                elif source.source_type == "whatsapp" and source.include_for_knowledge:

                    from whatsapp.models import WhatsAppMessage

                    chat_ids = source.metadata.get("chat_ids", [])
                    messages = WhatsAppMessage.objects.filter(
                        id__in=chat_ids, user=avatar.owner
                    )
                    logger.debug(f"WhatsApp: {messages.count()} messages.")

                    for msg in messages:
                        text = (msg.content or "").strip()
                        if not text:
                            continue

                        all_texts.append(text)

                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="whatsapp",
                            embedding=None,
                        )

        # --------------------------------------
        # Finalize avatar
        # --------------------------------------
        logger.info(f"Total text chunks processed: {len(all_texts)}")

        avatar.persona_prompt = (
            f"This is {avatar.name}. Persona trained from {len(all_texts)} inputs."
        )
        avatar.summary_knowledge = f"{len(all_texts)} memory chunks stored."
        avatar.trained = True
        avatar.trained_at = timezone.now()
        avatar.save()

        # --------------------------------------
        # Finish job
        # --------------------------------------
        job.status = "completed"
        job.finished_at = timezone.now()
        job.add_log(f"Training completed: {len(all_texts)} chunks processed.")
        logger.info(f"SUCCESS: Job {job.id} completed.")

    except Exception as e:
        # -------- ERROR HANDLING --------
        logger.error(
            f"FAILED: Training job {job.id} for avatar @{avatar.handle}: {str(e)}",
            exc_info=True,
        )

        job.status = "error"
        job.finished_at = timezone.now()
        job.add_log(f"Error during training: {str(e)}")
        job.save()

        avatar.trained = False
        avatar.save()
