from typing import List, Optional
from datetime import datetime
from .models import Reminder
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
