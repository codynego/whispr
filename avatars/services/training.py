# whisone/avatars/training.py

from avatars.models import Avatar, AvatarSource, AvatarMemoryChunk, AvatarTrainingJob
from django.utils import timezone
from django.db import transaction
import logging
from datetime import datetime

# ────────────────────── SAFE DEBUG PRINTER ──────────────────────
def dprint(msg: str):
    """Thread-safe debug print with timestamp – never shadows built-in print"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] [DEBUG] [AVATAR TRAINING] {msg}", flush=True)

logger = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────


def normalize_embeddings(value):
    if not value:
        return None
    if isinstance(value, list) and value and isinstance(value[0], float):
        return [value]
    if isinstance(value, list) and value and isinstance(value[0], list):
        return value
    return None


def train_avatar(avatar: Avatar, job: AvatarTrainingJob):
    dprint(f"STARTING training job {job.id} for avatar @{avatar.handle} (id={avatar.id})")

    job.status = "running"
    job.started_at = timezone.now()
    job.save()
    dprint("Job status → running")

    all_texts = []
    chunk_counter = 0

    try:
        sources = AvatarSource.objects.filter(avatar=avatar, enabled=True)
        dprint(f"Found {sources.count()} enabled sources for avatar")

        with transaction.atomic():
            dprint("Entered atomic transaction")

            for source_idx, source in enumerate(sources, start=1):
                dprint(f"[{source_idx}/{sources.count()}] Processing source id={source.id} | type={source.source_type} | knowledge={source.include_for_knowledge} | tone={source.include_for_tone}")

                # -------------------------
                # NOTES
                # -------------------------
                if source.source_type == "notes" and source.include_for_knowledge:
                    dprint("  → Handling NOTES source")
                    from whisone.models import Note

                    note_ids = source.metadata.get("ids", [])
                    dprint(f"    Looking for {len(note_ids)} note IDs")
                    notes = Note.objects.filter(id__in=note_ids, user=avatar.owner)

                    dprint(f"    Found {notes.count()} notes in DB")
                    for note in notes:
                        text = (note.content or "").strip()
                        if not text:
                            dprint(f"    Skipping empty note id={note.id}")
                            continue

                        all_texts.append(text)
                        chunk_counter += 1

                        embedding = normalize_embeddings(note.embedding)
                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="notes",
                            embedding=embedding,
                        )
                        dprint(f"    Created chunk #{chunk_counter} from note id={note.id} ({len(text.split())} words)")

                # -------------------------
                # FILE UPLOADS
                # -------------------------
                elif source.source_type == "uploads" and source.include_for_knowledge:
                    dprint("  → Handling UPLOADS source")
                    from whisone.models import UploadedFile

                    file_ids = source.metadata.get("ids", [])
                    dprint(f"    Requested {len(file_ids)} uploaded files")
                    files = UploadedFile.objects.filter(id__in=file_ids, user=avatar.owner)

                    dprint(f"    Retrieved {files.count()} uploaded files")
                    for f in files:
                        text = (f.content or "").strip()
                        if not text:
                            dprint(f"    Skipping empty file id={f.id} ({f.file.name})")
                            continue

                        all_texts.append(text)
                        chunk_counter += 1

                        embedding = normalize_embeddings(f.embedding)
                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="uploads",
                            embedding=embedding,
                        )
                        dprint(f"    Created chunk #{chunk_counter} from file id={f.id} | {f.file.name} ({len(text.split())} words)")

                # -------------------------
                # MANUAL Q&A (tone)
                # -------------------------
                elif source.source_type == "manual" and source.include_for_tone:
                    dprint("  → Handling MANUAL Q&A source (tone only)")
                    qa_list = source.metadata.get("qa_pairs", [])
                    dprint(f"    Found {len(qa_list)} Q&A pairs")

                    for i, qa in enumerate(qa_list):
                        q = qa.get("question", "").strip()
                        a = qa.get("answer", "").strip()
                        if not q and not a:
                            continue

                        text = f"Q: {q}\nA: {a}".strip()
                        all_texts.append(text)
                        chunk_counter += 1

                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="manual",
                            embedding=None,
                        )
                        dprint(f"    Created tone chunk #{chunk_counter} (pair {i+1})")

                # -------------------------
                # WHATSAPP
                # -------------------------
                elif source.source_type == "whatsapp" and source.include_for_knowledge:
                    dprint("  → Handling WHATSAPP source")
                    from whatsapp.models import WhatsAppMessage

                    chat_ids = source.metadata.get("chat_ids", [])
                    dprint(f"    Requested {len(chat_ids)} WhatsApp messages")
                    messages = WhatsAppMessage.objects.filter(id__in=chat_ids, user=avatar.owner)

                    dprint(f"    Retrieved {messages.count()} messages")
                    for msg in messages:
                        text = (msg.content or "").strip()
                        if not text:
                            continue

                        all_texts.append(text)
                        chunk_counter += 1

                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="whatsapp",
                            embedding=None,
                        )
                        dprint(f"    Created WhatsApp chunk #{chunk_counter} (msg id={msg.id})")

                else:
                    dprint(f"  → Source skipped (disabled or not selected for knowledge/tone)")

        # --------------------------------------
        # Finalize avatar
        # --------------------------------------
        dprint(f"Transaction committed. Total memory chunks created: {chunk_counter}")

        avatar.persona_prompt = f"This is {avatar.name}. Persona trained from {chunk_counter} inputs."
        avatar.summary_knowledge = f"{chunk_counter} memory chunks stored."
        avatar.trained = True
        avatar.trained_at = timezone.now()
        avatar.save()
        dprint("Avatar marked as trained and saved")

        # --------------------------------------
        # Finish job
        # --------------------------------------
        job.status = "completed"
        job.finished_at = timezone.now()
        job.add_log(f"Training completed successfully: {chunk_counter} chunks processed.")
        job.save()

        dprint(f"SUCCESS → Training job {job.id} finished with {chunk_counter} chunks")
        logger.info(f"Avatar training completed: @{avatar.handle} → {chunk_counter} chunks")

    except Exception as e:
        dprint(f"FATAL ERROR in training job {job.id}: {type(e).__name__}: {str(e)}")
        dprint("".join(traceback.format_exc().splitlines()[-10:]))  # last 10 lines of traceback

        logger.error(
            f"Training job {job.id} failed for @{avatar.handle}",
            exc_info=True
        )

        job.status = "error"
        job.finished_at = timezone.now()
        job.add_log(f"Error: {str(e)}")
        job.save()

        avatar.trained = False
        avatar.save(update_fields=["trained"])
        dprint("Job marked as error, avatar.trained = False")