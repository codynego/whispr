# assistant/automation_service.py
from datetime import datetime
from django.utils import timezone
from assistant.models import Automation
from django_celery_beat.models import (
    PeriodicTask,
    ClockedSchedule,
    IntervalSchedule,
    CrontabSchedule,
    SolarSchedule,
)
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
        action_type: str,
        name: str,
        trigger_type: str = "on_schedule",
        next_run_at: datetime = None,
        recurrence_pattern: str = None,
        trigger_condition: dict = None,
        action_params: dict = None,
        description: str = None,
    ) -> Optional[Automation]:
        """
        Creates a new automation instance and schedules it if applicable.
        
        Args:
            action_type: The type of action to perform (must match TASK_TYPE_CHOICES).
            name: Human-readable name for the automation.
            trigger_type: Type of trigger (e.g., 'on_schedule', 'on_email_received').
            next_run_at: Optional datetime for the next run (will be made timezone-aware if naive).
            recurrence_pattern: Optional cron-like pattern for recurring runs.
            trigger_condition: Optional dict of conditions for the trigger.
            action_params: Optional dict of parameters for the action.
            description: Optional detailed description.
        
        Returns:
            The created Automation instance or None on failure.
        """
        try:
            print(f"Creating automation: {action_type}, trigger: {trigger_type}")
            
            # Ensure next_run_at is timezone-aware if provided
            if next_run_at:
                if timezone.is_naive(next_run_at):
                    next_run_at = timezone.make_aware(next_run_at)
            
            automation = Automation.objects.create(
                user=self.user,
                action_type=action_type,
                name=name,
                trigger_type=trigger_type,
                next_run_at=next_run_at,
                recurrence_pattern=recurrence_pattern,
                trigger_condition=trigger_condition or {},
                action_params=action_params or {},
                description=description,
                is_active=True,
            )

            # Schedule if it's a time-based trigger
            if trigger_type == "on_schedule":
                self._schedule_automation(automation)

            logger.info(f"Automation created: {automation.id} ({automation.action_type})")
            return automation
        except ValidationError as ve:
            logger.error(f"Validation error creating automation: {ve}")
            return None
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
                if field in Automation._meta.get_fields():
                    setattr(automation, field, value)
            automation.save()

            # Reschedule if needed
            if any(key in updates for key in ["next_run_at", "recurrence_pattern"]):
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
    def trigger_automation(self, automation_id, context=None):
        """
        Manually triggers an automation. (Useful for 'on_message_received' or testing)
        Checks should_trigger first.
        """
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            if not automation.should_trigger(context):
                logger.info(f"Automation {automation_id} should not trigger under current conditions")
                return False

            # Execute logic here — e.g. send summary, follow-up, etc.
            self._execute_action(automation, context)
            automation.mark_triggered()
            return True
        except Exception as e:
            logger.error(f"Failed to trigger automation {automation_id}: {e}")
            return False

    # ------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------
    def _schedule_automation(self, automation):
        """Attach the automation to Celery Beat based on next_run_at and recurrence_pattern."""
        if not automation.next_run_at:
            return None

        # Delete any existing task first
        self._unschedule_automation(automation)

        task_name = f"automation_{automation.id}"
        args = json.dumps([automation.id])

        if automation.recurrence_pattern:
            # Handle recurring: assume recurrence_pattern is a cron string like "0 9 * * 1" for Mondays at 9am
            # Or simple patterns like "daily", "weekly", etc. — extend parser as needed
            schedule, created = CrontabSchedule.objects.get_or_create(
                crontab=automation.recurrence_pattern,
            )
            PeriodicTask.objects.create(
                crontab=schedule,
                name=task_name,
                task="assistant.tasks.execute_automation",
                args=args,
            )
        else:
            # One-time: use ClockedSchedule
            clocked, created = ClockedSchedule.objects.get_or_create(
                clocked_time=automation.next_run_at,
            )
            PeriodicTask.objects.create(
                clocked=clocked,
                name=task_name,
                task="assistant.tasks.execute_automation",
                args=args,
            )

    def _unschedule_automation(self, automation):
        """Remove any Celery Beat task linked to this automation."""
        PeriodicTask.objects.filter(name=f"automation_{automation.id}").delete()

    def _reschedule_automation(self, automation):
        """Recreate Celery Beat schedule."""
        self._unschedule_automation(automation)
        self._schedule_automation(automation)

    def _execute_action(self, automation, context=None):
        """Perform the actual action based on automation type."""
        action_type = automation.action_type
        params = automation.action_params or {}
        cond = automation.trigger_condition or {}

        # Examples of what to do (expand later)
        if action_type in ["reminder", "follow_up"]:
            # Send WhatsApp or email reminder, using params and context
            pass
        elif action_type == "auto_summarize":
            # Trigger summarize workflow, perhaps using context["text"]
            pass
        elif action_type == "smart_notify":
            # Send smart notifications based on cond and params
            pass
        else:
            logger.info(f"No handler defined for automation type: {action_type}")