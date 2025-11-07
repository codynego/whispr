# assistant/automation_service.py
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError
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
  # Ensure this is imported at the top (already there)

    def create_automation(
        self,
        action_type: str,
        name: str,
        trigger_type: str = "on_schedule",
        next_run_at: datetime | str = None,  # Accept str for LLM outputs
        recurrence_pattern: str = None,
        trigger_condition: dict = None,
        action_params: dict = None,
        description: str = None,
    ) -> Automation | None:
        """
        Creates a new automation instance and schedules it if applicable.
        
        Args:
            action_type: The type of action to perform (must match TASK_TYPE_CHOICES).
            name: Human-readable name for the automation.
            trigger_type: Type of trigger (e.g., 'on_schedule', 'on_email_received').
            next_run_at: Optional datetime or ISO string for the next run (will be parsed and made timezone-aware if naive).
            recurrence_pattern: Optional cron-like pattern for recurring runs.
            trigger_condition: Optional dict of conditions for the trigger.
            action_params: Optional dict of parameters for the action.
            description: Optional detailed description.
        
        Returns:
            The created Automation instance or None on failure.
        """
        try:
            print(f"Creating automation: {action_type}, trigger: {trigger_type}")
            
            # Parse and ensure next_run_at is a timezone-aware datetime if provided
            if next_run_at:
                if isinstance(next_run_at, str):
                    # Parse ISO string (e.g., '2025-11-08T22:00:00') to datetime
                    try:
                        next_run_at = datetime.fromisoformat(next_run_at)
                    except ValueError as parse_err:
                        logger.error(f"Invalid next_run_at format '{next_run_at}': {parse_err}")
                        return None
                
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
    def update_automation(self, automation_id: int, **updates) -> Automation | None:
        """
        Updates an existing automation and reschedules if necessary.
        
        Args:
            automation_id: ID of the automation to update.
            **updates: Keyword arguments for fields to update (e.g., action_type='new_type').
        
        Returns:
            The updated Automation instance or None on failure.
        """
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            
            # Update only valid fields
            for field, value in updates.items():
                if field in [f.name for f in Automation._meta.fields]:
                    setattr(automation, field, value)
            
            # Handle timezone-aware datetime updates
            if "next_run_at" in updates and updates["next_run_at"]:
                if timezone.is_naive(updates["next_run_at"]):
                    updates["next_run_at"] = timezone.make_aware(updates["next_run_at"])
                setattr(automation, "next_run_at", updates["next_run_at"])
            
            automation.save()

            # Reschedule if schedule-related fields changed
            if any(key in updates for key in ["next_run_at", "recurrence_pattern", "trigger_type"]):
                if automation.trigger_type == "on_schedule":
                    self._reschedule_automation(automation)

            logger.info(f"Automation updated: {automation_id}")
            return automation
        except Automation.DoesNotExist:
            logger.warning(f"Automation {automation_id} not found for user {self.user}")
            return None
        except ValidationError as ve:
            logger.error(f"Validation error updating automation {automation_id}: {ve}")
            return None
        except Exception as e:
            logger.error(f"Failed to update automation {automation_id}: {e}")
            return None

    # ------------------------------------------------
    # DELETE AUTOMATION
    # ------------------------------------------------
    def delete_automation(self, automation_id: int) -> bool:
        """
        Deletes an automation and unschedules it.
        
        Args:
            automation_id: ID of the automation to delete.
        
        Returns:
            True on success, False otherwise.
        """
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            self._unschedule_automation(automation)
            automation.delete()
            logger.info(f"Automation deleted: {automation_id}")
            return True
        except Automation.DoesNotExist:
            logger.warning(f"Automation {automation_id} not found for user {self.user}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete automation {automation_id}: {e}")
            return False

    # ------------------------------------------------
    # TRIGGER AUTOMATION
    # ------------------------------------------------
    def trigger_automation(self, automation_id: int, context: dict = None) -> bool:
        """
        Manually triggers an automation after checking conditions.
        
        Args:
            automation_id: ID of the automation to trigger.
            context: Optional context dict for condition checks (e.g., {'sender': 'user@example.com'}).
        
        Returns:
            True if triggered successfully, False otherwise.
        """
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            if not automation.should_trigger(context):
                logger.info(f"Automation {automation_id} should not trigger under current conditions")
                return False

            self._execute_action(automation, context)
            automation.mark_triggered()
            logger.info(f"Automation {automation_id} triggered successfully")
            return True
        except Automation.DoesNotExist:
            logger.warning(f"Automation {automation_id} not found for user {self.user}")
            return False
        except Exception as e:
            logger.error(f"Failed to trigger automation {automation_id}: {e}")
            return False

    # ------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------
    def _schedule_automation(self, automation: Automation) -> None:
        """Attach the automation to Celery Beat based on next_run_at and recurrence_pattern."""
        if not automation.next_run_at:
            logger.warning(f"No next_run_at set for automation {automation.id}; skipping schedule")
            return

        # Delete any existing task first
        self._unschedule_automation(automation)

        task_name = f"automation_{automation.id}"
        args = json.dumps([automation.id])

        try:
            if automation.recurrence_pattern:
                # Handle recurring: assume recurrence_pattern is a cron string
                # (Extend with parser for natural language like 'daily' if needed)
                schedule, _ = CrontabSchedule.objects.get_or_create(
                    crontab=automation.recurrence_pattern,
                )
                PeriodicTask.objects.create(
                    crontab=schedule,
                    name=task_name,
                    task="assistant.tasks.execute_automation",
                    args=args,
                )
                logger.debug(f"Recurring task scheduled for automation {automation.id}: {automation.recurrence_pattern}")
            else:
                # One-time: use ClockedSchedule
                clocked, _ = ClockedSchedule.objects.get_or_create(
                    clocked_time=automation.next_run_at,
                )
                PeriodicTask.objects.create(
                    clocked=clocked,
                    name=task_name,
                    task="assistant.tasks.execute_automation",
                    args=args,
                    one_off=True,  # Required for one-time clocked tasks
                )
                logger.debug(f"One-time task scheduled for automation {automation.id} at {automation.next_run_at}")
        except Exception as e:
            logger.error(f"Failed to schedule automation {automation.id}: {e}")

    def _unschedule_automation(self, automation: Automation) -> None:
        """Remove any Celery Beat task linked to this automation."""
        deleted_count, _ = PeriodicTask.objects.filter(name=f"automation_{automation.id}").delete()
        if deleted_count > 0:
            logger.debug(f"Unscheduled {deleted_count} task(s) for automation {automation.id}")

    def _reschedule_automation(self, automation: Automation) -> None:
        """Recreate Celery Beat schedule after changes."""
        self._unschedule_automation(automation)
        self._schedule_automation(automation)

    def _execute_action(self, automation: Automation, context: dict = None) -> None:
        """
        Perform the actual action based on automation type.
        
        Args:
            automation: The Automation instance.
            context: Optional context for action execution.
        """
        action_type = automation.action_type
        params = automation.action_params or {}
        trigger_cond = automation.trigger_condition or {}

        logger.info(f"Executing action '{action_type}' for automation {automation.id}")

        # Dispatch based on action_type (expand with real implementations)
        if action_type in ["reminder", "follow_up"]:
            # Example: Send WhatsApp/email reminder using params and context
            # e.g., self.message_service.send_reminder(params.get('channel'), **params)
            logger.info(f"Reminder/follow-up sent via {params.get('channel', 'default')}")
        elif action_type == "auto_summarize":
            # Example: Trigger summarize workflow on context['text']
            text_to_summarize = context.get("text", "") if context else ""
            # e.g., summary = self.llm_service.summarize(text_to_summarize)
            logger.info(f"Summary generated for text length: {len(text_to_summarize)}")
        elif action_type == "smart_notify":
            # Example: Send notifications based on conditions and params
            # e.g., self.notification_service.notify(trigger_cond, params)
            logger.info("Smart notification dispatched")
        else:
            logger.warning(f"No handler defined for action type: {action_type}")