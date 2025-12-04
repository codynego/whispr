# tasks.py

from celery import shared_task, group, chord # <--- NEW IMPORTS!
from django.utils import timezone
from whisone.models import UploadedFile

from openai import OpenAI
from django.conf import settings

import os
from pathlib import Path
import pdfplumber
import traceback
from datetime import datetime

# NOTE: Removed docx, pytesseract, PIL imports for brevity, 
# but ensure you keep all original imports needed for file handling.

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def debug_print(msg):
    """Helper to always see debug output with timestamp"""
    # Use self.request.id if available for task-specific logging
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] [DEBUG] [TASK] {msg}")


# ----------------------------
# Chunking helper (No changes needed)
# ----------------------------
def chunk_text(text, chunk_size=800, overlap=150):
    debug_print("Starting chunk_text")
    words = text.split()
    chunks = []
    start = 0
    
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    
    debug_print(f"chunk_text finished → {len(chunks)} chunks")
    return chunks


# ----------------------------
# Embedding helper (No changes needed)
# ----------------------------
def embed_chunk(chunk: str):
    debug_print(f"Embedding chunk of {len(chunk.split())} words...")
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=chunk
        )
        embedding = response.data[0].embedding
        debug_print(f"Embedding successful | dim={len(embedding)}")
        return embedding
    except Exception as e:
        debug_print(f"ERROR in embed_chunk: {type(e).__name__}: {str(e)}")
        raise


# ========================================================
# NEW Task 1 — Process, Chunk, and Embed a SINGLE Page (The Parallel Worker)
# ========================================================
@shared_task(bind=True)
def process_page_and_embed(self, file_id, page_content, page_num, total_pages):
    """
    Handles Chunking and Embedding for one page. This task runs in parallel.
    """
    debug_print(f"PAGE TASK STARTED for file_id={file_id} | Page {page_num}/{total_pages}")
    
    # 1. Chunk text
    chunks = chunk_text(page_content)

    # 2. Embed each chunk
    embeddings = []
    for idx, chunk in enumerate(chunks, start=1):
        # This is the most time-consuming part (OpenAI API call)
        emb = embed_chunk(chunk)
        embeddings.append(emb)
    
    debug_print(f"PAGE TASK FINISHED for Page {page_num}: {len(chunks)} chunks, {len(embeddings)} embeddings.")
    
    # Return the page's content and its embeddings to the finalizer
    return {
        'page_num': page_num,
        'text': page_content,
        'embeddings': embeddings
    }


# ========================================================
# NEW Task 2 — Final Callback (The Collector/Finalizer)
# ========================================================
@shared_task(bind=True)
def finalize_file_processing(self, results_list, file_id):
    """
    Collects results from all parallel page tasks and saves the final data.
    """
    debug_print(f"FINALIZER STARTED for file_id={file_id}. Aggregating results...")
    
    # Aggregate all data
    full_text_list = []
    all_embeddings = []
    
    # Sort results by page number to maintain document order (if available in results)
    sorted_results = sorted([r for r in results_list if isinstance(r, dict)], key=lambda x: x.get('page_num', 0))
    
    for result in sorted_results:
        full_text_list.append(result['text'])
        all_embeddings.extend(result['embeddings'])
            
    final_text = "\n".join(full_text_list).strip()
    total_words = len(final_text.split())
    total_chunks = len(all_embeddings)

    # Save to database
    try:
        uploaded_file = UploadedFile.objects.get(id=file_id)
        uploaded_file.content = final_text
        uploaded_file.embedding = all_embeddings
        uploaded_file.processed = True
        uploaded_file.save(update_fields=["content", "embedding", "processed"])
        
        debug_print(f"FINALIZER SUCCESS: Total words={total_words}, Total chunks={total_chunks}")

        return {
            "status": "success",
            "file_id": file_id,
            "chunks": total_chunks,
            "words": total_words,
            "message": "Processing and embedding completed"
        }
    except Exception as e:
        debug_print(f"FINALIZER FAILED: {e}")
        raise


# ========================================================
# MODIFIED Main Task — Dispatcher
# ========================================================
@shared_task(bind=True)
def process_uploaded_file(self, file_id):
    """
    Extracts pages sequentially, then dispatches parallel page tasks using a Chord.
    """
    debug_print(f"DISPATCHER STARTED for file_id={file_id}")

    try:
        uploaded_file = UploadedFile.objects.get(id=file_id)
        file_path = uploaded_file.file.path
        
        # --- 1. Sequential Extraction ---
        extracted_pages = [] # List of text strings, one per page
        
        if uploaded_file.file_type == "pdf":
            debug_print("Extracting PDF with pdfplumber (to get page list)...")
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    t = page.extract_text()
                    if t:
                        extracted_pages.append(t)
                        # No longer embedding here, just extracting text!
            
        elif uploaded_file.file_type == "docx":
             # Your existing sequential logic for DOCX to get one large text block
             # and then wrapping it in a list to treat as a single "page"
             # Example: extracted_pages.append(doc_text)
             pass 
        
        # ... (Include logic for other file types here, treating them as one or more pages)
        
        # --- 2. Parallel Dispatch via Chord ---
        total_pages = len(extracted_pages)
        if not total_pages:
            debug_print("No content to process. Dispatching skipped.")
            # Handle empty file finalization here
            return

        debug_print(f"Dispatching {total_pages} page tasks in parallel using Chord...")
        
        # 1. Header (The Group of parallel tasks)
        page_signatures = [
            process_page_and_embed.s(file_id, page_content, i, total_pages) 
            for i, page_content in enumerate(extracted_pages, start=1)
        ]
        
        # 2. Workflow (Group | Finalizer)
        # 
        workflow = chord(
            group(page_signatures),
            finalize_file_processing.s(file_id=file_id) # The callback (Body)
        )
        
        # 3. Launch the workflow
        workflow.apply_async()

        result = {
            "status": "dispatched",
            "file_id": file_id,
            "total_pages": total_pages,
            "message": f"Processing of {total_pages} pages dispatched via Celery Chord."
        }
        debug_print(f"DISPATCHER FINISHED → {result}")
        return result

    except UploadedFile.DoesNotExist:
        error_msg = f"File with id {file_id} not found."
        debug_print(f"ERROR: {error_msg}")
        return {"status": "error", "message": error_msg}

    except Exception as e:
        error_msg = f"FATAL ERROR in dispatcher: {type(e).__name__}: {str(e)}"
        debug_print(error_msg)
        raise