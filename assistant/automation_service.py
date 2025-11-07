# assistant/automation_service.py
from datetime import datetime
from django.utils import timezone
from assistant.models import Automation
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
import json
import logging

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Central service to create, update, delete and trigger automations.
    Automations are lightweight, can be user-triggered or system-triggered.
    """

    def __init__(self, user):
        self.user = user

    # ------------------------------------------------
    # CREATE AUTOMATION
    # ------------------------------------------------
    def create_automation(
        self,
        task_type: str,
        title: str,
        trigger_type: str = "on_schedule",
        due_datetime: datetime = None,
        is_recurring: bool = False,
        recurrence_pattern: str = None,
        metadata: dict = None,
    ):
        try:
            automation = Automation.objects.create(
                user=self.user,
                task_type=task_type,
                title=title,
                trigger_type=trigger_type,
                due_datetime=due_datetime,
                is_recurring=is_recurring,
                recurrence_pattern=recurrence_pattern,
                metadata=metadata or {},
                status="active",
            )

            # If it's scheduled — create a Celery Beat entry
            if trigger_type == "on_schedule":
                self._schedule_automation(automation)

            logger.info(f"Automation created: {automation.id} ({automation.task_type})")
            return automation
        except Exception as e:
            logger.error(f"Failed to create automation: {e}")
            return None

    # ------------------------------------------------
    # UPDATE AUTOMATION
    # ------------------------------------------------
    def update_automation(self, automation_id, **updates):
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            for field, value in updates.items():
                setattr(automation, field, value)
            automation.save()

            # Reschedule if needed
            if "due_datetime" in updates or "recurrence_pattern" in updates:
                self._reschedule_automation(automation)

            return automation
        except Automation.DoesNotExist:
            logger.warning(f"Automation {automation_id} not found for user {self.user}")
            return None
        except Exception as e:
            logger.error(f"Failed to update automation {automation_id}: {e}")
            return None

    # ------------------------------------------------
    # DELETE AUTOMATION
    # ------------------------------------------------
    def delete_automation(self, automation_id):
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            self._unschedule_automation(automation)
            automation.delete()
            logger.info(f"Automation deleted: {automation_id}")
            return True
        except Automation.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Failed to delete automation {automation_id}: {e}")
            return False

    # ------------------------------------------------
    # TRIGGER AUTOMATION
    # ------------------------------------------------
    def trigger_automation(self, automation_id):
        """
        Manually triggers an automation. (Useful for 'on_message_received' or testing)
        """
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            # Execute logic here — e.g. send summary, follow-up, etc.
            self._execute_action(automation)
            automation.last_triggered = timezone.now()
            automation.save()
            return True
        except Exception as e:
            logger.error(f"Failed to trigger automation {automation_id}: {e}")
            return False

    # ------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------
    def _schedule_automation(self, automation):
        """Attach the automation to Celery Beat if due_datetime is set."""
        if not automation.due_datetime:
            return None

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=automation.due_datetime.minute,
            hour=automation.due_datetime.hour,
            day_of_month=automation.due_datetime.day,
            month_of_year=automation.due_datetime.month,
        )

        PeriodicTask.objects.create(
            crontab=schedule,
            name=f"automation_{automation.id}",
            task="assistant.tasks.execute_automation",
            args=json.dumps([automation.id]),
        )

    def _unschedule_automation(self, automation):
        """Remove any Celery Beat task linked to this automation."""
        PeriodicTask.objects.filter(name=f"automation_{automation.id}").delete()

    def _reschedule_automation(self, automation):
        """Recreate Celery Beat schedule."""
        self._unschedule_automation(automation)
        self._schedule_automation(automation)

    def _execute_action(self, automation):
        """Perform the actual action based on automation type."""
        task_type = automation.task_type
        data = automation.metadata or {}

        # Examples of what to do (expand later)
        if task_type in ["reminder", "follow_up"]:
            # Send WhatsApp or email reminder
            pass
        elif task_type == "auto_summarize":
            # Trigger summarize workflow
            pass
        elif task_type == "smart_notify":
            # Send smart notifications
            pass
        else:
            logger.info(f"No handler defined for automation type: {task_type}")
