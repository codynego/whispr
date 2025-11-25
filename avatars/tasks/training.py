# avatars/tasks/training.py
from celery import shared_task
from django.utils import timezone
from openai import OpenAI
from avatars.models import Avatar, AvatarTrainingJob, AvatarMemoryChunk
import textwrap

client = OpenAI()

CHUNK_SIZE = 800  # tokens ≈ characters / 4 → safe for embedding

def chunk_text(text: str):
    """Simple but effective chunking"""
    words = text.split()
    current = []
    current_len = 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len > CHUNK_SIZE:
            yield " ".join(current)
            current = []
            current_len = 0
    if current:
        yield " ".join(current)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_avatar_training(self, job_id: str):
    job = AvatarTrainingJob.objects.get(id=job_id)
    avatar = job.avatar

    try:
        job.status = "running"
        job.started_at = timezone.now()
        job.save()

        job.add_log("Starting training...")

        # 1. Collect all text from enabled sources
        all_text = []
        for source in avatar.sources.filter(enabled=True, include_for_knowledge=True):
            # Replace with real integrations later
            sample = source.metadata.get("sample_data", [])
            if isinstance(sample, list):
                all_text.extend(sample)
            job.add_log(f"Loaded {source.get_source_type_display()}")

        full_text = "\n\n".join(all_text)
        if not full_text.strip():
            raise ValueError("No training data found. Connect sources first.")

        job.add_log(f"Total training data: {len(full_text):,} characters")

        # 2. Chunk + embed
        job.add_log("Chunking & embedding...")
        AvatarMemoryChunk.objects.filter(avatar=avatar).delete()

        chunks = list(chunk_text(full_text))
        embeddings = client.embeddings.create(
            model="text-embedding-3-large",
            input=chunks
        ).data

        for chunk_text, emb in zip(chunks, embeddings):
            AvatarMemoryChunk.objects.create(
                avatar=avatar,
                text=chunk_text,
                source_type="training",
                embedding=emb.embedding,
                metadata={"source": "training_run"}
            )

        # 3. Generate persona & style
        job.add_log("Analyzing personality & writing style...")

        persona = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.3,
            messages=[
                {"role": "system", "content": textwrap.dedent("""
                You are an expert personality analyst.
                From the text below, extract in first-person:
                - How I talk (tone, energy, slang)
                - My core values and beliefs
                - How I respond to questions
                - My humor style
                Keep it natural, concise, and usable as a system prompt.
                """)},
                {"role": "user", "content": full_text[:32000]}
            ]
        ).choices[0].message.content

        style = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.0,
            messages=[
                {"role": "system", "content": "Summarize the writing style in 2–3 sentences: sentence length, emojis, formatting, warmth level, etc."},
                {"role": "user", "content": full_text[:16000]}
            ]
        ).choices[0].message.content

        # 4. Save everything
        avatar.persona_prompt = persona.strip()
        avatar.writing_style = style.strip()
        avatar.summary_knowledge = full_text[:4000]
        avatar.trained = True
        avatar.trained_at = timezone.now()
        avatar.save()

        job.status = "completed"
        job.finished_at = timezone.now()
        job.add_log("Training completed successfully!")
        job.save()

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.add_log(f"Training failed: {e}")
        job.save()
        raise  # Celery will retry