import re
from django.shortcuts import get_object_or_404
from whisone.models import UploadedFile
from whisone.tasks.chat_with_file import chat_with_file

def handle_file_command(user, message_text):
    """
    Handles /file commands:
    - /file list -> returns user's files
    - /file <filename> <query> -> queries a specific file
    - /file <query> -> queries most recent file if filename not provided
    """
    message_text = message_text.strip()
    response = ""


    # If user wants list of files
    if message_text.lower() == "list":
        files = UploadedFile.objects.filter(user=user).order_by('-uploaded_at')
        if not files.exists():
            return "You have no uploaded files."
        file_list = "\n".join([f"{i+1}. {f.original_filename}" for i, f in enumerate(files)])
        return f"Your uploaded files:\n{file_list}"

    # Check if user typed "/file filename query"
    match = re.match(r"([\w\.\-]+)\s+(.*)", message_text)
    if match:
        filename_candidate = match.group(1)
        query = match.group(2).strip()
        try:
            file = UploadedFile.objects.get(user=user, original_filename__iexact=filename_candidate)
            answer = chat_with_file(file, query)
            return answer
        except UploadedFile.DoesNotExist:
            return f"File '{filename_candidate}' not found. Use '/file list' to see your files."

    # If no filename given, use the most recent uploaded file
    most_recent_file = UploadedFile.objects.filter(user=user).order_by('-uploaded_at').first()
    if most_recent_file:
        query = message_text
        answer = chat_with_file(most_recent_file, query)
        return answer
    else:
        return "You have no uploaded files to query. Use '/file list' to upload files first."

