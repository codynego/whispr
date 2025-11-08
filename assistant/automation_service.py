# assistant/automation_service.py
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError
from assistant.models import Automation
from django_celery_beat.models import (
    PeriodicTask,
    ClockedSchedule,
    CrontabSchedule,
)
import json
import logging

logger = logging.getLogger(__name__)

class AutomationService:
    """
    Central service to create, update, delete and trigger automations.
    Supports multi-step workflows defined in automation.workflow JSON.
    """

    def __init__(self, user):
        self.user = user

    # ------------------------------------------------
    # CREATE AUTOMATION
    # ------------------------------------------------
    def create_automation(
        self,
        name: str,
        workflow: dict,
        trigger_type: str = "on_schedule",
        next_run_at: datetime | str = None,
        recurrence_pattern: str = None,
        description: str = None,
        is_active: bool = True,
    ) -> Automation | None:
        """
        Create a new automation with a multi-step workflow.
        """
        try:
            logger.info(f"Creating automation: {name}, trigger: {trigger_type}")

            # Parse and ensure next_run_at is timezone-aware
            if next_run_at:
                if isinstance(next_run_at, str):
                    try:
                        next_run_at = datetime.fromisoformat(next_run_at)
                    except ValueError as e:
                        logger.error(f"Invalid next_run_at format '{next_run_at}': {e}")
                        return None
                if timezone.is_naive(next_run_at):
                    next_run_at = timezone.make_aware(next_run_at)

            automation = Automation.objects.create(
                user=self.user,
                name=name,
                workflow=workflow or {},
                trigger_type=trigger_type,
                next_run_at=next_run_at,
                recurrence_pattern=recurrence_pattern,
                description=description,
                is_active=is_active,
            )

            # Schedule if time-based
            if trigger_type == "on_schedule":
                self._schedule_automation(automation)

            logger.info(f"Automation created: {automation.id}")
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
        Update existing automation and reschedule if needed.
        """
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)

            for field, value in updates.items():
                if field in [f.name for f in Automation._meta.fields]:
                    setattr(automation, field, value)

            # Handle timezone for next_run_at
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
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            if not automation.should_trigger(context):
                logger.info(f"Automation {automation_id} should not trigger under current conditions")
                return False

            self._execute_workflow(automation, context)
            automation.last_triggered_at = timezone.now()
            automation.save()
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
        if not automation.next_run_at:
            logger.warning(f"No next_run_at set for automation {automation.id}; skipping schedule")
            return

        self._unschedule_automation(automation)

        task_name = f"automation_{automation.id}"
        args = json.dumps([automation.id])

        try:
            if automation.recurrence_pattern:
                # Assume cron string
                schedule, _ = CrontabSchedule.objects.get_or_create(crontab=automation.recurrence_pattern)
                PeriodicTask.objects.create(
                    crontab=schedule,
                    name=task_name,
                    task="assistant.tasks.execute_automation",
                    args=args,
                )
                logger.debug(f"Recurring task scheduled for automation {automation.id}")
            else:
                clocked, _ = ClockedSchedule.objects.get_or_create(clocked_time=automation.next_run_at)
                PeriodicTask.objects.create(
                    clocked=clocked,
                    name=task_name,
                    task="assistant.tasks.execute_automation",
                    args=args,
                    one_off=True,
                )
                logger.debug(f"One-time task scheduled for automation {automation.id} at {automation.next_run_at}")
        except Exception as e:
            logger.error(f"Failed to schedule automation {automation.id}: {e}")

    def _unschedule_automation(self, automation: Automation) -> None:
        deleted_count, _ = PeriodicTask.objects.filter(name=f"automation_{automation.id}").delete()
        if deleted_count > 0:
            logger.debug(f"Unscheduled {deleted_count} task(s) for automation {automation.id}")

    def _reschedule_automation(self, automation: Automation) -> None:
        self._unschedule_automation(automation)
        self._schedule_automation(automation)

    def _execute_workflow(self, automation: Automation, context: dict = None) -> None:
        """
        Execute all actions defined in automation.workflow
        """
        workflow = automation.workflow or {}
        actions = workflow.get("actions", [])
        context = context or {}

        logger.info(f"Executing workflow for automation {automation.id} with {len(actions)} actions")

        for idx, action in enumerate(actions, start=1):
            action_type = action.get("type")
            config = action.get("config", {})

            logger.info(f"Action {idx}/{len(actions)}: {action_type} | config: {config}")

            if action_type == "reminder":
                channel = config.get("channel", "default")
                logger.info(f"Sending reminder via {channel}")
                # TODO: integrate actual send logic

            elif action_type == "extract_fields":
                fields = config.get("fields", [])
                text = context.get("text", "")
                extracted = {field: f"dummy_{field}" for field in fields}  # placeholder
                context.update(extracted)
                logger.info(f"Extracted fields: {extracted}")

            elif action_type == "append_google_sheet":
                spreadsheet_name = config.get("spreadsheet_name")
                columns = config.get("columns", [])
                row_data = {col: context.get(col) for col in columns}
                logger.info(f"Appending to Google Sheet '{spreadsheet_name}': {row_data}")
                # TODO: integrate actual Google Sheets API

            elif action_type == "send_whatsapp_message":
                msg_template = config.get("message_template", "")
                for k, v in context.items():
                    msg_template = msg_template.replace(f"{{{{{k}}}}}", str(v))
                logger.info(f"Sending WhatsApp message: {msg_template}")
                # TODO: integrate WhatsApp API

            elif action_type == "append_notion_page":
                database_name = config.get("database_name")
                fields_mapping = config.get("fields_mapping", {})
                row_data = {k: context.get(v) for k, v in fields_mapping.items()}
                logger.info(f"Appending page to Notion '{database_name}': {row_data}")
                # TODO: integrate Notion API

            else:
                logger.warning(f"No handler for action type: {action_type}")
