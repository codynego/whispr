# whisone/avatars/training.py
from avatars.models import Avatar, AvatarSource, AvatarMemoryChunk, AvatarTrainingJob
from django.utils import timezone
# Import the standard Python logging module
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)


def train_avatar(avatar: Avatar, job: AvatarTrainingJob):
    """
    Processes all enabled sources for the Avatar and updates memory chunks & persona.
    """
    
    # ---------------------
    # START DEBUG LOG
    # ---------------------
    logger.info(f"STARTING training job {job.id} for avatar: @{avatar.handle}")
    # print(f"STARTING training job {job.id} for avatar: @{avatar.handle}") # Alternative if only print() works
    # ---------------------
    
    job.status = "running"
    job.started_at = timezone.now()
    job.save()

    all_texts = []

    try:
        sources = AvatarSource.objects.filter(avatar=avatar, enabled=True)
        
        # DEBUG: Log the number of sources found
        logger.info(f"Found {sources.count()} enabled sources for processing.")

        for source in sources:
            
            # DEBUG: Log the processing of a specific source
            logger.info(f"Processing source: ID={source.id}, Type={source.source_type}, Knowledge={source.include_for_knowledge}, Tone={source.include_for_tone}")

            # ---------------------
            # Notes
            # ---------------------
            if source.source_type == "notes" and source.include_for_knowledge:

                note_ids = source.metadata.get("note_ids", [])
                print(f"Note IDs to process: {note_ids}")  # DEBUG print statement
                from whisone.models import Note
                print(f"Fetching Notes for Avatar Owner ID: {avatar.owner.id}")  # DEBUG print statement
                notes = Note.objects.filter(id__in=note_ids, user=avatar.owner)
                print(f"Retrieved {notes.count()} Notes from DB")  # DEBUG print statement
                
                # DEBUG: Log number of items retrieved for this source
                logger.debug(f"Notes: Retrieved {notes.count()} notes.")
                
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
                file_ids = source.metadata.get("ids", [])
                print(f"File IDs to process: {file_ids}")  # DEBUG print statement
                print(f"Fetching UploadedFiles for Avatar Owner ID: {avatar.owner.id}")  # DEBUG print statement
                from whisone.models import UploadedFile
                files = UploadedFile.objects.filter(id__in=file_ids, user=avatar.owner)
                print(f"Retrieved {files.count()} UploadedFiles from DB")  # DEBUG print statement
                
                # DEBUG: Log number of items retrieved for this source
                logger.debug(f"Files: Retrieved {files.count()} files.")
                
                for f in files:
                    text = f.content()  # implement extract_text in your model
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
                
                # DEBUG: Log number of items retrieved for this source
                logger.debug(f"Manual: Retrieved {len(qa_list)} Q&A pairs.")

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
                messages = WhatsAppMessage.objects.filter(id__in=chat_ids, user=avatar.owner)
                
                # DEBUG: Log number of items retrieved for this source
                logger.debug(f"WhatsApp: Retrieved {messages.count()} messages.")

                for msg in messages:
                    text = msg.content.strip()
                    all_texts.append(text)
                    AvatarMemoryChunk.objects.create(
                        avatar=avatar,
                        text=text,
                        source_type="whatsapp"
                    )

        # ---------------------
        # Finalization & Completion
        # ---------------------
        
        # DEBUG: Log total text count before saving avatar
        logger.info(f"Total text chunks processed: {len(all_texts)}")
        
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
        
        # FINAL DEBUG LOG
        logger.info(f"SUCCESS: Training job {job.id} completed.")
        
    except Exception as e:
        # ---------------------
        # Error Handling
        # ---------------------
        
        # ERROR DEBUG LOG
        logger.error(f"FAILURE: Training job {job.id} failed with error: {str(e)}", exc_info=True)
        
        job.status = "error"
        job.finished_at = timezone.now()
        job.add_log(f"Error during training: {str(e)}")
        job.save() # Save the job status update
        
        avatar.trained = False
        avatar.save() # Save the avatar trained status update