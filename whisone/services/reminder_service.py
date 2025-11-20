from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from whisone.models import Reminder
from django.contrib.auth.models import User
from whisone.utils.embedding_utils import generate_embedding


class ReminderService:
    def __init__(self, user: User):
        self.user = user

    # -------------------------
    # CRUD
    # -------------------------
    def create_reminder(self, text: str, remind_at: datetime) -> Reminder:
        """
        Creates a reminder and generates an embedding for semantic search.
        """
        embedding = generate_embedding(text)
        reminder = Reminder.objects.create(
            user=self.user,
            text=text,
            remind_at=remind_at,
            embedding=embedding
        )
        return reminder

    def update_reminder(
        self, reminder_id: int, text: str = None, remind_at: datetime = None
    ) -> Optional[Reminder]:
        """
        Updates a reminder. Regenerates embedding if text changes.
        """
        try:
            reminder = Reminder.objects.get(id=reminder_id, user=self.user)
            if text:
                reminder.text = text
                reminder.embedding = generate_embedding(text)
            if remind_at:
                reminder.remind_at = remind_at
            reminder.save()
            return reminder
        except Reminder.DoesNotExist:
            return None

    def delete_reminder(self, reminder_id: int) -> bool:
        try:
            reminder = Reminder.objects.get(id=reminder_id, user=self.user)
            reminder.delete()
            return True
        except Reminder.DoesNotExist:
            return False

    # -------------------------
    # Fetch / Search
    # -------------------------
    def fetch_reminders(self, filters: Optional[List[Dict[str, Any]]] = None) -> List[Reminder]:
        """
        Supports filters:
        - keyword: text__icontains
        - after: remind_at >= datetime
        - before: remind_at <= datetime
        - completed: True/False
        """
        qs = Reminder.objects.filter(user=self.user)

        if filters:
            for f in filters:
                if isinstance(f, dict):
                    # Legacy {"key": ..., "value": ...}
                    if "key" in f and "value" in f:
                        key = f["key"].lower()
                        value = f["value"]
                    # Direct {filter_type: value}
                    else:
                        items = list(f.items())
                        if not items:
                            continue
                        key, value = items[0]
                        key = key.lower()

                    if key == "keyword" and value:
                        qs = qs.filter(text__icontains=value)
                    elif key == "after" and value:
                        dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
                        qs = qs.filter(remind_at__gte=dt)
                    elif key == "before" and value:
                        dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
                        qs = qs.filter(remind_at__lte=dt)
                    elif key == "completed" and isinstance(value, bool):
                        qs = qs.filter(completed=value)

        return qs.order_by("remind_at")

    # -------------------------
    # Utility
    # -------------------------
    def list_reminders(self) -> List[Reminder]:
        return Reminder.objects.filter(user=self.user).order_by("remind_at")

    def get_due_reminders(self, current_time: datetime) -> List[Reminder]:
        return Reminder.objects.filter(user=self.user, remind_at__lte=current_time, completed=False)

    def get_upcoming_reminders(self, hours: int = 24) -> List[Reminder]:
        now = datetime.now()
        max_time = now + timedelta(hours=hours)
        return (
            Reminder.objects.filter(
                user=self.user,
                remind_at__gt=now,
                remind_at__lte=max_time,
                completed=False
            )
            .order_by("remind_at")
        )
