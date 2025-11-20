from typing import List, Optional, Dict, Any
from whisone.models import Note
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from whisone.utils.embedding_utils import generate_embedding


class NoteService:
    def __init__(self, user: User):
        self.user = user

    # -------------------------
    # CRUD
    # -------------------------
    def create_note(self, content: str) -> Note:
        """
        Creates a note and generates an embedding.
        """
        embedding = generate_embedding(content)
        note = Note.objects.create(
            user=self.user,
            content=content,
            embedding=embedding
        )
        return note

    def update_note(self, note_id: int, new_content: str) -> Optional[Note]:
        """
        Updates note content AND regenerates embedding.
        """
        try:
            note = Note.objects.get(id=note_id, user=self.user)
            note.content = new_content
            note.embedding = generate_embedding(new_content)
            note.save()
            return note
        except Note.DoesNotExist:
            return None

    def delete_note(self, note_id: int) -> bool:
        """
        Deletes a note. Returns True if success.
        """
        try:
            note = Note.objects.get(id=note_id, user=self.user)
            note.delete()
            return True
        except Note.DoesNotExist:
            return False

    # -------------------------
    # Fetch / Search
    # -------------------------
    def fetch_notes(self, filters: Optional[List[Dict[str, Any]]] = None) -> List[Note]:
        """
        Filter notes by:
        - keyword (icontains)
        - after (created_at >= datetime)
        - before (created_at <= datetime)
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
                        dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
                        qs = qs.filter(created_at__gte=dt)
                    except Exception:
                        continue

                elif key == "before" and value:
                    try:
                        dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
                        qs = qs.filter(created_at__lte=dt)
                    except Exception:
                        continue

        return qs.order_by("-created_at")

    def search_notes(self, keyword: str) -> List[Note]:
        """
        Simple keyword search.
        (Semantic search will be added in resolver instead.)
        """
        return Note.objects.filter(user=self.user, content__icontains=keyword)

    def get_recent_notes(self, hours: int = 24) -> List[Note]:
        """
        Returns notes created within the last `hours` time window.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        return (
            Note.objects.filter(user=self.user, created_at__gte=cutoff)
            .order_by("-created_at")
        )
