# tasks.py

from celery import shared_task, group, chord # <--- ADDED group and chord for parallel processing
from django.utils import timezone
from whisone.models import UploadedFile

from openai import OpenAI
from django.conf import settings

import os
from pathlib import Path
from docx import Document
import pdfplumber
import pytesseract
from PIL import Image
import traceback
from datetime import datetime


client = OpenAI(api_key=settings.OPENAI_API_KEY)


def debug_print(msg):
    """Helper to always see debug output with timestamp"""
    # NOTE: The task name is now generic since this function is used by multiple tasks
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] [DEBUG] [TASK] {msg}")


# --- Helper functions (No changes needed) ---
# ----------------------------
# Chunking helper
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
        debug_print(f"Created chunk {len(chunks)} | words {start}-{min(end, len(words))} | length {len(chunk.split())} words")
        start += chunk_size - overlap
    
    debug_print(f"chunk_text finished → {len(chunks)} chunks")
    return chunks


# ----------------------------
# Embedding helper
# ----------------------------
def embed_chunk(chunk: str):
    debug_print(f"Embedding chunk of {len(chunk.split())} words (~{len(chunk)} chars)")
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
        debug_print(traceback.format_exc())
        # Re-raise to mark the task as failed
        raise


# ========================================================
# NEW Task 1 — Process, Chunk, and Embed a SINGLE Page (The Parallel Worker)
# ========================================================
@shared_task(bind=True)
def process_page_and_embed(self, file_id, page_content, page_num, total_pages):
    """
    Handles Chunking and Embedding for one page/text-block. Runs in parallel.
    """
    debug_print(f"PAGE TASK STARTED for file_id={file_id} | Page {page_num}/{total_pages}")
    
    # 1. Chunk text
    chunks = chunk_text(page_content)

    # 2. Embed each chunk (This is the slow, API-intensive part that is now parallelized)
    embeddings = []
    for idx, chunk in enumerate(chunks, start=1):
        emb = embed_chunk(chunk)
        embeddings.append(emb)
    
    debug_print(f"PAGE TASK FINISHED for Page {page_num}: {len(chunks)} chunks, {len(embeddings)} embeddings.")
    
    # Return the page's content and its embeddings to the finalizer task
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
    Collects results from all parallel page tasks, aggregates them, and saves to DB.
    """
    debug_print(f"FINALIZER STARTED for file_id={file_id}. Aggregating results...")
    
    full_text_list = []
    all_embeddings = []
    
    # Sort results by page number to maintain document order
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
        
        # Save all results
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
# MODIFIED Main Task — Dispatcher (Extracts pages and launches the Chord)
# ========================================================
@shared_task(bind=True)
def process_uploaded_file(self, file_id):
    """
    Extracts content from uploaded file and dispatches parallel page-processing tasks.
    """
    debug_print(f"DISPATCHER STARTED for file_id={file_id}")

    try:
        uploaded_file = UploadedFile.objects.get(id=file_id)
        file_path = uploaded_file.file.path
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File does not exist: {file_path}")

        extracted_pages = [] # This list will hold (text_content, page_number) for dispatch

        # ----------------------------------------
        # 1. Sequential Text Extraction (Must happen first)
        # ----------------------------------------
        if uploaded_file.file_type == "pdf":
            debug_print("Extracting PDF with pdfplumber...")
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    t = page.extract_text()
                    if t:
                        extracted_pages.append((t, i))
                        debug_print(f"    Page {i} extracted {len(t.split())} words")

        elif uploaded_file.file_type == "docx":
            debug_print("Extracting DOCX with python-docx...")
            doc = Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = "\n".join(paragraphs)
            # Treat DOCX as a single page/block for processing
            if full_text:
                 extracted_pages.append((full_text, 1)) 

        elif uploaded_file.file_type in ["txt", "csv"]:
            debug_print("Reading plain text file...")
            with open(file_path, "r", encoding="utf-8") as f:
                full_text = f.read()
            # Treat simple text files as a single page/block
            if full_text:
                extracted_pages.append((full_text, 1))

        elif uploaded_file.file_type == "image":
            debug_print("Running OCR with pytesseract...")
            img = Image.open(file_path)
            full_text = pytesseract.image_to_string(img)
            # Treat images as a single page/block
            if full_text:
                extracted_pages.append((full_text, 1))

        # --- Handle empty content and unknown types (Refactored) ---
        if not extracted_pages:
            debug_print("No content extracted from file. Marking as processed.")
            uploaded_file.processed = True
            uploaded_file.save(update_fields=["processed"])
            return {"status": "success", "message": "No text found for embedding."}
        
        # ----------------------------------------
        # 2. Parallel Dispatch via Chord
        # ----------------------------------------
        total_pages = len(extracted_pages)
        debug_print(f"Dispatching {total_pages} content blocks in parallel...")
        
        # 1. Header (The Group of parallel page tasks)
        page_signatures = [
            process_page_and_embed.s(file_id, content, page_num, total_pages) 
            for content, page_num in extracted_pages
        ]
        
        # 2. Workflow (Group | Finalizer)
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
            "message": f"Processing of {total_pages} content blocks dispatched via Celery Chord."
        }
        debug_print(f"DISPATCHER FINISHED → {result}")
        return result

    except UploadedFile.DoesNotExist:
        error_msg = f"File with id {file_id} not found in database."
        debug_print(f"ERROR: {error_msg}")
        return {"status": "error", "message": error_msg}

    except Exception as e:
        error_msg = f"FATAL ERROR in dispatcher: {type(e).__name__}: {str(e)}"
        debug_print(error_msg)
        debug_print(traceback.format_exc())
        return {"status": "error", "message": error_msg, "traceback": traceback.format_exc()}