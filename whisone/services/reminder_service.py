from typing import List, Optional, Dict, Any
from datetime import datetime
from whisone.models import Reminder
from django.contrib.auth.models import User

class ReminderService:
    def __init__(self, user: User):
        self.user = user

    def create_reminder(self, text: str, remind_at: datetime) -> Reminder:
        reminder = Reminder.objects.create(user=self.user, text=text, remind_at=remind_at)
        return reminder

    def update_reminder(self, reminder_id: int, text: str = None, remind_at: datetime = None) -> Optional[Reminder]:
        try:
            reminder = Reminder.objects.get(id=reminder_id, user=self.user)
            if text:
                reminder.text = text
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

    def list_reminders(self) -> List[Reminder]:
        return Reminder.objects.filter(user=self.user).order_by('remind_at')

    def get_due_reminders(self, current_time: datetime) -> List[Reminder]:
        return Reminder.objects.filter(user=self.user, remind_at__lte=current_time, completed=False)

    # ------------------------- 
    # Fetch / Search with filters
    # -------------------------
    def fetch_reminders(self, filters: Optional[List[Dict[str, Any]]] = None) -> List[Reminder]:
        """
        filters: list of dicts, e.g.
        [
            {"key": "keyword", "value": "meeting"},
            {"key": "after", "value": "2025-11-01T00:00"},
            {"key": "before", "value": "2025-11-15T23:59"}
        ]
        """
        qs = Reminder.objects.filter(user=self.user)

        if filters:
            for f in filters:
                key = f.get("key", "").lower()
                value = f.get("value", "")
                if key == "keyword" and value:
                    qs = qs.filter(text__icontains=value)
                elif key == "after" and value:
                    try:
                        dt = datetime.fromisoformat(value)
                        qs = qs.filter(remind_at__gte=dt)
                    except ValueError:
                        continue
                elif key == "before" and value:
                    try:
                        dt = datetime.fromisoformat(value)
                        qs = qs.filter(remind_at__lte=dt)
                    except ValueError:
                        continue

        return qs.order_by('remind_at')
