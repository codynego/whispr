from typing import List, Optional, Dict, Any
from datetime import datetime
from whisone.models import Reminder
from django.contrib.auth.models import User
from datetime import datetime, timedelta

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
        filters: list of dicts, supporting both formats:
        - Legacy: [{"key": "keyword", "value": "meeting"}]
        - Direct: [{"keyword": "meeting"}, {"after": "2025-11-01T00:00"}]
        """
        qs = Reminder.objects.filter(user=self.user)

        if filters:
            for f in filters:
                if isinstance(f, dict):
                    # Handle legacy {"key": ..., "value": ...}
                    if "key" in f and "value" in f:
                        key = f.get("key", "").lower()
                        value = f.get("value", "")
                    # Handle direct {filter_type: value}
                    else:
                        # Assume first item is key/value if single pair
                        items = list(f.items())
                        if items:
                            key, value = items[0]
                            key = key.lower()
                        else:
                            continue
                    
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
                    # Add more filter types here if needed (e.g., "completed": True/False)

        return qs.order_by('remind_at')

    def get_upcoming_reminders(self, hours: int = 24) -> List[Reminder]:
        """
        Returns reminders scheduled within the next `hours` window.
        Default: next 24 hours.
        """
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