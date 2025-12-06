# whisone/avatars/training.py

from avatars.models import Avatar, AvatarSource, AvatarMemoryChunk, AvatarTrainingJob
from django.utils import timezone
from django.db import transaction
import logging
from datetime import datetime
import traceback

# Your embedding function
from whisone.utils.embedding_utils import generate_embedding as get_embedding

def dprint(msg: str):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] [DEBUG] [AVATAR TRAINING] {msg}", flush=True)

logger = logging.getLogger(__name__)

def normalize_embeddings(value):
    if not value:
        return None
    if isinstance(value, list) and value and isinstance(value[0], float):
        return [value]
    if isinstance(value, list) and value and isinstance(value[0], list):
        return value
    return None

def split_text_into_chunks(text: str, max_tokens: int = 1000, overlap: int = 100):
    words = text.split()
    chunks = []
    current = []
    current_tokens = 0
    for word in words:
        current.append(word)
        current_tokens += 1
        if current_tokens >= max_tokens:
            chunks.append(" ".join(current))
            current = current[-overlap:] if overlap > 0 else []
            current_tokens = len(current)
    if current:
        chunks.append(" ".join(current))
    return chunks


def train_avatar(avatar: Avatar, job: AvatarTrainingJob):
    dprint(f"STARTING training job {job.id} for avatar @{avatar.handle} (id={avatar.id})")

    job.status = "running"
    job.started_at = timezone.now()
    job.save()

    chunk_counter = 0

    try:
        sources = AvatarSource.objects.filter(avatar=avatar, enabled=True)
        dprint(f"Found {sources.count()} enabled sources")

        with transaction.atomic():
            for source_idx, source in enumerate(sources, start=1):
                st = source.source_type
                dprint(f"[{source_idx}/{sources.count()}] Processing source id={source.id} | type={st} | knowledge={source.include_for_knowledge} | tone={source.include_for_tone}")

                # ————————————————————————
                # 1. RAW TEXT
                # ————————————————————————
                if st == "text":
                    texts = source.metadata.get("content", "") or source.metadata.get("texts", [])
                    if isinstance(texts, str):
                        texts = [texts]
                    for block in texts:
                        text = str(block).strip()
                        if not text:
                            continue
                        chunks = split_text_into_chunks(text)
                        for chunk in chunks:
                            embedding = None
                            if source.include_for_knowledge:
                                try:
                                    embedding = normalize_embeddings(get_embedding(chunk))
                                except Exception as e:
                                    dprint(f"Embedding failed for text chunk: {e}")
                            AvatarMemoryChunk.objects.create(
                                avatar=avatar,
                                text=chunk,
                                source_type="text",
                                source_id=source.id,
                                embedding=embedding,
                                metadata={"used_for_knowledge": source.include_for_knowledge, "used_for_tone": source.include_for_tone}
                            )
                            chunk_counter += 1

                # ————————————————————————
                # 2. NOTES
                # ————————————————————————
                elif st == "notes" and source.include_for_knowledge:
                    from whisone.models import Note
                    for note in Note.objects.filter(id__in=source.metadata.get("item_ids", []), user=avatar.owner):
                        text = (note.content or "").strip()
                        if not text: continue
                        embedding = normalize_embeddings(note.embedding) if source.include_for_knowledge else None
                        AvatarMemoryChunk.objects.create(
                            avatar=avatar, text=text, source_type="notes", source_id=note.id, embedding=embedding
                        )
                        chunk_counter += 1

                # ————————————————————————
                # 3. UPLOADS
                # ————————————————————————
                elif st == "uploads" and source.include_for_knowledge:
                    from whisone.models import UploadedFile
                    for f in UploadedFile.objects.filter(id__in=source.metadata.get("item_ids", []), user=avatar.owner):
                        text = (f.content or "").strip()
                        if not text: continue
                        embedding = normalize_embeddings(f.embedding) if source.include_for_knowledge else None
                        AvatarMemoryChunk.objects.create(
                            avatar=avatar, text=text, source_type="uploads", source_id=f.id, embedding=embedding
                        )
                        chunk_counter += 1

                # ————————————————————————
                # 4. REMINDERS (NEW!)
                # ————————————————————————
                elif st == "reminders" and (source.include_for_knowledge or source.include_for_tone):
                    from whisone.models import Reminder  # adjust import as needed

                    reminder_ids = source.metadata.get("item_ids", [])
                    for rem in Reminder.objects.filter(id__in=reminder_ids, user=avatar.owner):
                        parts = []
                        if rem.title:
                            parts.append(f"Reminder: {rem.title}")
                        if rem.text:
                            parts.append(rem.text)
                        if rem.remind_at:
                            due = rem.remind_at.strftime("%Y-%m-%d %H:%M") if rem.remind_at else "no due date"
                            parts.append(f"Due: {due}")
                        if rem.completed:
                            parts.append("Status: completed")
                        else:
                            parts.append("Status: pending")

                        text = " | ".join(parts).strip()
                        if not text:
                            continue

                        embedding = None
                        if source.include_for_knowledge:
                            try:
                                embedding = normalize_embeddings(get_embedding(text))
                            except Exception as e:
                                dprint(f"Failed to embed reminder {rem.id}: {e}")

                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="reminders",
                            source_id=rem.id,
                            embedding=embedding,
                            metadata={"completed": rem.completed, "due_date": rem.due_date.isoformat() if rem.due_date else None}
                        )
                        chunk_counter += 1
                        dprint(f"    Added reminder chunk: {text[:100]}...")

                # ————————————————————————
                # 5. TODOS (NEW!)
                # ————————————————————————
                elif st == "todos" and (source.include_for_knowledge or source.include_for_tone):
                    from whisone.models import Todo  # adjust import

                    todo_ids = source.metadata.get("item_ids", [])
                    for todo in Todo.objects.filter(id__in=todo_ids, user=avatar.owner):
                        parts = []
                        if todo.title:
                            parts.append(f"Todo: {todo.title}")
                        if todo.task:
                            parts.append(todo.task)
                        # if todo.due_date:
                        #     due = todo.due_date.strftime("%Y-%m-%d")
                        #     parts.append(f"Due: {due}")
                        status = "completed" if todo.done else "pending"
                        parts.append(f"Status: {status}")

                        text = " | ".join(parts).strip()
                        if not text:
                            continue

                        embedding = None
                        if source.include_for_knowledge:
                            try:
                                embedding = normalize_embeddings(get_embedding(text))
                            except Exception as e:
                                dprint(f"Failed to embed todo {todo.id}: {e}")

                        AvatarMemoryChunk.objects.create(
                            avatar=avatar,
                            text=text,
                            source_type="todos",
                            source_id=todo.id,
                            embedding=embedding,
                            metadata={"completed": todo.completed, "due_date": todo.due_date.isoformat() if todo.due_date else None}
                        )
                        chunk_counter += 1
                        dprint(f"    Added todo chunk: {text[:100]}...")


                # ————————————————————————
                # 7. WHATSAPP
                # ————————————————————————
                elif st == "whatsapp" and source.include_for_knowledge:
                    from whatsapp.models import WhatsAppMessage
                    for msg in WhatsAppMessage.objects.filter(id__in=source.metadata.get("item_ids", []), user=avatar.owner):
                        text = (msg.content or "").strip()
                        if not text: continue
                        AvatarMemoryChunk.objects.create(
                            avatar=avatar, text=text, source_type="whatsapp", source_id=msg.id, embedding=None
                        )
                        chunk_counter += 1

        # ——— Finalize ———
        avatar.summary_knowledge = f"{chunk_counter} memory chunks (notes, files, text, reminders, todos, etc.)"
        avatar.trained = True
        avatar.trained_at = timezone.now()
        avatar.save()

        job.status = "completed"
        job.finished_at = timezone.now()
        job.add_log(f"Training completed: {chunk_counter} chunks processed.")
        job.save()

        dprint(f"SUCCESS → Training job {job.id} finished with {chunk_counter} chunks")
        logger.info(f"Avatar @{avatar.handle} trained successfully → {chunk_counter} chunks")

    except Exception as e:
        tb = "".join(traceback.format_exc().splitlines()[-10:])
        dprint(f"ERROR in training job {job.id}: {e}\n{tb}")
        logger.error(f"Training failed for @{avatar.handle}", exc_info=True)

        job.status = "error"
        job.finished_at = timezone.now()
        job.add_log(f"Training failed: {str(e)}")
        job.save()

        avatar.trained = False
        avatar.save(update_fields=["trained"])