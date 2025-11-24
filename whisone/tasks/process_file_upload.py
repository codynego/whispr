# tasks.py
from celery import shared_task
from django.utils import timezone
from .models import UploadedFile
from whisone.utils.embedding_utils import generate_embedding

import os
from pathlib import Path
from docx import Document
import pdfplumber
import pytesseract
from PIL import Image

@shared_task
def process_uploaded_file(file_id):
    """
    Extracts text from an uploaded file, updates the UploadedFile.content field,
    and generates embeddings for it.
    """
    try:
        uploaded_file = UploadedFile.objects.get(id=file_id)
        file_path = uploaded_file.file.path
        text = ""

        # ----------------------------
        # Extract text by file type
        # ----------------------------
        if uploaded_file.file_type == "pdf":
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

        elif uploaded_file.file_type == "docx":
            doc = Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs if p.text])

        elif uploaded_file.file_type in ["txt", "csv"]:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

        elif uploaded_file.file_type == "image":
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)

        else:
            # Unknown type → attempt reading as text
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()

        # Clean text
        text = text.strip()

        # Update UploadedFile
        uploaded_file.content = text
        uploaded_file.embedding = generate_embedding(text) if text else None
        uploaded_file.processed = True
        uploaded_file.save(update_fields=["content", "embedding", "processed"])

        return {"status": "success", "file_id": file_id, "words": len(text.split())}

    except UploadedFile.DoesNotExist:
        return {"status": "error", "message": f"File with id {file_id} not found."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
