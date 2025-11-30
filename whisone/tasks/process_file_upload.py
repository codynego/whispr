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

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ----------------------------
# Chunking helper
# ----------------------------
def chunk_text(text, chunk_size=800, overlap=150):
    """
    Split long text into overlapping chunks.
    Returns: ["chunk1", "chunk2", ...]
    """
    words = text.split()
    chunks = []
    start = 0
    
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    
    return chunks


# ----------------------------
# Embedding helper
# ----------------------------
def embed_chunk(chunk: str):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunk
    )
    return response.data[0].embedding


# ========================================================
# Main Task — Extract + Chunk + Embed
# ========================================================
@shared_task
def process_uploaded_file(file_id):
    """
    Extract text from uploaded file → chunk → embed → save.
    """
    try:
        uploaded_file = UploadedFile.objects.get(id=file_id)
        file_path = uploaded_file.file.path
        text = ""

        # ----------------------------------------
        # Extract text based on file type
        # ----------------------------------------
        if uploaded_file.file_type == "pdf":
            extracted_pages = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        extracted_pages.append(t)
            text = "\n".join(extracted_pages)

        elif uploaded_file.file_type == "docx":
            doc = Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs if p.text)

        elif uploaded_file.file_type in ["txt", "csv"]:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

        elif uploaded_file.file_type == "image":
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)

        else:
            # Unknown → try read as text
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

        # Clean
        text = text.strip()

        # Store full extracted text
        uploaded_file.content = text

        # If no text → still mark as processed
        if not text:
            uploaded_file.embedding = None
            uploaded_file.processed = True
            uploaded_file.save(update_fields=["content", "embedding", "processed"])
            return {
                "status": "success",
                "file_id": file_id,
                "words": 0,
                "chunks": 0
            }

        # ----------------------------------------
        # Chunk text
        # ----------------------------------------
        chunks = chunk_text(text)

        # ----------------------------------------
        # Embed each chunk
        # ----------------------------------------
        embeddings = []
        for chunk in chunks:
            emb = embed_chunk(chunk)
            embeddings.append(emb)

        # Save embeddings (list of lists)
        uploaded_file.embedding = embeddings
        uploaded_file.processed = True
        uploaded_file.save(update_fields=["content", "embedding", "processed"])

        return {
            "status": "success",
            "file_id": file_id,
            "chunks": len(chunks),
            "words": len(text.split())
        }

    except UploadedFile.DoesNotExist:
        return {"status": "error", "message": f"File with id {file_id} not found."}

    except Exception as e:
        return {"status": "error", "message": str(e)}
