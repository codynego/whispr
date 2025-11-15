from typing import List, Optional
from .models import Note
from django.contrib.auth.models import User

class NoteService:
    def __init__(self, user: User):
        self.user = user

    def create_note(self, content: str) -> Note:
        note = Note.objects.create(user=self.user, content=content)
        return note

    def update_note(self, note_id: int, new_content: str) -> Optional[Note]:
        try:
            note = Note.objects.get(id=note_id, user=self.user)
            note.content = new_content
            note.save()
            return note
        except Note.DoesNotExist:
            return None

    def delete_note(self, note_id: int) -> bool:
        try:
            note = Note.objects.get(id=note_id, user=self.user)
            note.delete()
            return True
        except Note.DoesNotExist:
            return False

    def search_notes(self, keyword: str) -> List[Note]:
        return Note.objects.filter(user=self.user, content__icontains=keyword)

    def list_notes(self) -> List[Note]:
        return Note.objects.filter(user=self.user).order_by('-created_at')
