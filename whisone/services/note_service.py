from typing import List, Optional, Dict, Any
from whisone.models import Note
from django.contrib.auth.models import User
from datetime import datetime


class NoteService:
    def __init__(self, user: User):
        self.user = user

    # -------------------------
    # CRUD
    # -------------------------
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

    # -------------------------
    # Fetch / Search with filters
    # -------------------------
    def fetch_notes(self, filters: Optional[List[Dict[str, Any]]] = None) -> List[Note]:
        """
        filters: list of dicts, e.g.
        [
            {"key": "keyword", "value": "meeting"},
            {"key": "after", "value": "2025-11-01T00:00"},
            {"key": "before", "value": "2025-11-15T23:59"}
        ]
        """
        qs = Note.objects.filter(user=self.user)

        if filters:
            for f in filters:
                key = f.get("key", "").lower()
                value = f.get("value", "")
                if key == "keyword" and value:
                    qs = qs.filter(content__icontains=value)
                elif key == "after" and value:
                    try:
                        dt = datetime.fromisoformat(value)
                        qs = qs.filter(created_at__gte=dt)
                    except ValueError:
                        continue
                elif key == "before" and value:
                    try:
                        dt = datetime.fromisoformat(value)
                        qs = qs.filter(created_at__lte=dt)
                    except ValueError:
                        continue

        return qs.order_by('-created_at')

    def search_notes(self, keyword: str) -> List[Note]:
        return Note.objects.filter(user=self.user, content__icontains=keyword)
