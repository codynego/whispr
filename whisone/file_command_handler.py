import re
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

    # If user wants list of files
    if message_text.lower() == "list":
        files = UploadedFile.objects.filter(user=user).order_by('-uploaded_at')
        if not files.exists():
            return "You have no uploaded files."
        file_list = "\n".join([f"{i+1}. {f.original_filename}" for i, f in enumerate(files)])
        return f"Your uploaded files:\n{file_list}"

    # Attempt to find filename from user's uploaded files
    files = UploadedFile.objects.filter(user=user)
    matched_file = None
    query = ""
    for f in files:
        if message_text.lower().startswith(f.original_filename.lower()):
            matched_file = f
            query = message_text[len(f.original_filename):].strip()
            break

    if matched_file:
        if not query:
            return f"You asked for '{matched_file.original_filename}' but didn't provide a query. Please add a question after the filename."
        return chat_with_file(matched_file, query)

    # If no file matches, use most recent file
    most_recent_file = files.order_by('-uploaded_at').first()
    if most_recent_file:
        return chat_with_file(most_recent_file, message_text)
    else:
        return "You have no uploaded files to query. Use '/file list' to upload files first."
