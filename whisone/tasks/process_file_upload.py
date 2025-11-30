# tasks.py
from celery import shared_task
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
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] [DEBUG] [TASK process_uploaded_file] {msg}")


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
        raise


# ========================================================
# Main Task — Extract + Chunk + Embed
# ========================================================
@shared_task(bind=True)
def process_uploaded_file(self, file_id):
    """
    Extract text from uploaded file → chunk → embed → save.
    """
    debug_print(f"TASK STARTED for file_id={file_id}")

    try:
        debug_print("Fetching UploadedFile from DB...")
        uploaded_file = UploadedFile.objects.get(id=file_id)
        debug_print(f"Found UploadedFile: {uploaded_file.id} | name={uploaded_file.file.name} | type={uploaded_file.file_type}")

        file_path = uploaded_file.file.path
        debug_print(f"File path resolved: {file_path}")
        if not os.path.exists(file_path):
            debug_print("FILE NOT FOUND ON DISK!")
            raise FileNotFoundError(f"File does not exist: {file_path}")

        text = ""
        debug_print(f"Starting text extraction for type: {uploaded_file.file_type}")

        # ----------------------------------------
        # Extract text based on file type
        # ----------------------------------------
        if uploaded_file.file_type == "pdf":
            debug_print("Extracting PDF with pdfplumber...")
            extracted_pages = []
            try:
                with pdfplumber.open(file_path) as pdf:
                    debug_print(f"PDF opened → {len(pdf.pages)} pages")
                    for i, page in enumerate(pdf.pages, start=1):
                        debug_print(f"  Processing page {i}/{len(pdf.pages)}")
                        t = page.extract_text()
                        if t:
                            extracted_pages.append(t)
                            debug_print(f"    Page {i} extracted {len(t.split())} words")
                        else:
                            debug_print(f"    Page {i} → no text")
                text = "\n".join(extracted_pages)
                debug_print(f"PDF extraction complete → total {len(text.split())} words")
            except Exception as e:
                debug_print(f"PDF extraction failed: {e}")
                raise

        elif uploaded_file.file_type == "docx":
            debug_print("Extracting DOCX with python-docx...")
            try:
                doc = Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                text = "\n".join(paragraphs)
                debug_print(f"DOCX extracted → {len(paragraphs)} paragraphs, {len(text.split())} words")
            except Exception as e:
                debug_print(f"DOCX extraction failed: {e}")
                raise

        elif uploaded_file.file_type in ["txt", "csv"]:
            debug_print("Reading plain text file...")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
                debug_print(f"Text file read → {len(text.split())} words")
            except Exception as e:
                debug_print(f"Text file read failed: {e}")
                raise

        elif uploaded_file.file_type == "image":
            debug_print("Running OCR with pytesseract...")
            try:
                img = Image.open(file_path)
                debug_print(f"Image opened: {img.size} | mode={img.mode}")
                text = pytesseract.image_to_string(img)
                debug_print(f"OCR complete → {len(text.split())} words extracted")
            except Exception as e:
                debug_print(f"OCR failed: {e}")
                raise

        else:
            debug_print(f"Unknown file type '{uploaded_file.file_type}', trying as raw text...")
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                debug_print(f"Fallback text read → {len(text.split())} words")
            except Exception as e:
                debug_print(f"Fallback read failed: {e}")
                raise

        # Clean whitespace
        text = text.strip()
        debug_print(f"Final extracted text length: {len(text)} chars, {len(text.split())} words")

        # Store full extracted text
        uploaded_file.content = text
        uploaded_file.save(update_fields=["content"])
        debug_print("Saved extracted content to DB")

        # If no text → still mark as processed
        if not text:
            debug_print("No text extracted → marking as processed with null embedding")
            uploaded_file.embedding = None
            uploaded_file.processed = True
            uploaded_file.save(update_fields=["embedding", "processed"])

            result = {
                "status": "success",
                "file_id": file_id,
                "words": 0,
                "chunks": 0,
                "message": "No text found"
            }
            debug_print(f"TASK FINISHED (empty) → {result}")
            return result

        # ----------------------------------------
        # Chunk text
        # ----------------------------------------
        debug_print("Starting chunking...")
        chunks = chunk_text(text)
        debug_print(f"Chunking done → {len(chunks)} chunks created")

        # ----------------------------------------
        # Embed each chunk
        # ----------------------------------------
        debug_print("Starting embedding of all chunks...")
        embeddings = []
        for idx, chunk in enumerate(chunks, start=1):
            debug_print(f"Embedding chunk {idx}/{len(chunks)}...")
            emb = embed_chunk(chunk)
            embeddings.append(emb)

        debug_print(f"All {len(embeddings)} chunks embedded successfully")

        # Save embeddings
        uploaded_file.embedding = embeddings
        uploaded_file.processed = True
        uploaded_file.save(update_fields=["embedding", "processed"])
        debug_print("Embeddings saved to DB")

        result = {
            "status": "success",
            "file_id": file_id,
            "chunks": len(chunks),
            "words": len(text.split()),
            "message": "Processing completed"
        }
        debug_print(f"TASK SUCCESSFULLY FINISHED → {result}")
        return result

    except UploadedFile.DoesNotExist:
        error_msg = f"File with id {file_id} not found in database."
        debug_print(f"ERROR: {error_msg}")
        return {"status": "error", "message": error_msg}

    except Exception as e:
        error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
        debug_print(f"FATAL ERROR: {error_msg}")
        debug_print(traceback.format_exc())
        return {"status": "error", "message": error_msg, "traceback": traceback.format_exc()}