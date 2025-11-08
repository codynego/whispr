from datetime import datetime, timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from assistant.models import Automation
from django_celery_beat.models import (
    PeriodicTask,
    ClockedSchedule,
    CrontabSchedule,
)
from dateutil.rrule import rrule, WEEKLY, MO  # For advanced scheduling
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AutomationService:
    """
    Central service to create, update, delete and trigger automations.
    Supports multi-step workflows defined in automation.action_params JSON.
    """

    def __init__(self, user):
        self.user = user
        self.action_registry = self._register_actions()  # Dynamic action handlers

    # ---------------- ACTION REGISTRY ---------------- #
    def _register_actions(self) -> Dict[str, callable]:
        """Registry for executable actions; extend with real integrations."""
        return {
            "reminder": self._execute_reminder,
            "extract_fields": self._execute_extract_fields,
            "append_google_sheet": self._execute_append_google_sheet,
            "send_whatsapp_message": self._execute_send_whatsapp_message,
            "fetch_calendar_events": self._execute_fetch_calendar_events,
            "append_notion_page": self._execute_append_notion_page,
            "fetch_unread_emails": self._execute_fetch_unread_emails,
            "summarize_messages": self._execute_summarize_messages,
            "create_calendar_event": self._execute_create_calendar_event,  # New
            "send_email": self._execute_send_email,  # New
            "fetch_last_week_reports": self._execute_fetch_last_week_reports,  # New
        }

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
        trigger_condition: dict = None,
    ) -> Automation | None:
        """
        Create a new automation with a multi-step workflow.
        Saves workflow to action_params JSONField.
        """
        try:
            logger.info(f"Creating automation: {name}, trigger: {trigger_type}")

            # Parse and ensure next_run_at is timezone-aware
            if next_run_at:
                if isinstance(next_run_at, str):
                    try:
                        next_run_at = datetime.fromisoformat(next_run_at.replace('Z', '+00:00'))
                    except ValueError as e:
                        logger.error(f"Invalid next_run_at format '{next_run_at}': {e}")
                        return None
                if timezone.is_naive(next_run_at):
                    next_run_at = timezone.make_aware(next_run_at)

            # Prepare action_params (full workflow)
            action_params = workflow or {}
            if trigger_condition:
                action_params.setdefault("trigger", {}).setdefault("config", trigger_condition)

            automation = Automation.objects.create(
                user=self.user,
                name=name,
                action_params=action_params,  # Save workflow here
                trigger_type=trigger_type,
                next_run_at=next_run_at,
                recurrence_pattern=recurrence_pattern,
                description=description,
                is_active=is_active,
            )

            # Schedule if time-based
            if trigger_type == "on_schedule" and is_active:
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

            # Handle workflow/action_params update
            if "workflow" in updates:
                updates["action_params"] = {**automation.action_params, **updates["workflow"]} if automation.action_params else updates["workflow"]
                del updates["workflow"]

            for field, value in updates.items():
                if field in [f.name for f in Automation._meta.fields]:
                    setattr(automation, field, value)

            # Handle timezone for next_run_at
            if "next_run_at" in updates and updates["next_run_at"]:
                if isinstance(updates["next_run_at"], str):
                    try:
                        updates["next_run_at"] = datetime.fromisoformat(updates["next_run_at"].replace('Z', '+00:00'))
                    except ValueError:
                        pass
                if timezone.is_naive(updates["next_run_at"]):
                    updates["next_run_at"] = timezone.make_aware(updates["next_run_at"])
                setattr(automation, "next_run_at", updates["next_run_at"])

            automation.save()

            # Reschedule if schedule-related fields changed
            if any(key in updates for key in ["next_run_at", "recurrence_pattern", "trigger_type", "is_active"]):
                if automation.trigger_type == "on_schedule" and automation.is_active:
                    self._reschedule_automation(automation)
                elif not automation.is_active:
                    self._unschedule_automation(automation)

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

            self._execute_workflow(automation, context or {})
            automation.last_triggered_at = timezone.now()
            automation.save(update_fields=["last_triggered_at"])

            # Reschedule next run for recurring
            if automation.recurrence_pattern and automation.trigger_type == "on_schedule":
                automation.next_run_at = self._compute_next_run(automation)
                automation.save(update_fields=["next_run_at"])
                self._reschedule_automation(automation)

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
                # Parse pattern to Crontab (e.g., "weekly on Monday" → "0 11 * * 1")
                cron_str = self._pattern_to_cron(automation.recurrence_pattern, automation.action_params.get("trigger", {}).get("config", {}))
                if cron_str:
                    schedule, _ = CrontabSchedule.objects.get_or_create(crontab=cron_str)
                    PeriodicTask.objects.create(
                        crontab=schedule,
                        name=task_name,
                        task="assistant.tasks.execute_automation",
                        args=args,
                    )
                    logger.debug(f"Recurring task scheduled for automation {automation.id} with cron: {cron_str}")
                else:
                    logger.warning(f"Could not parse recurrence '{automation.recurrence_pattern}' for {automation.id}")
            else:
                # One-off clocked task
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

    def _pattern_to_cron(self, pattern: str, trigger_config: dict) -> str:
        """Convert recurrence_pattern to Crontab string (e.g., 'weekly on Monday' → '0 11 * * 1')."""
        time_parts = trigger_config.get("time", "00:00").split(":")
        minute = int(time_parts[0])
        hour = int(time_parts[1]) if len(time_parts) > 1 else 0

        if "daily" in pattern:
            return f"{minute} {hour} * * *"
        elif "weekly on Monday" in pattern:
            return f"{minute} {hour} * * 1"  # Monday=1
        elif "weekly" in pattern and "Monday" in pattern:
            return f"{minute} {hour} * * 1"
        # Extend for more patterns (e.g., rrule to cron conversion)
        return None

    def _compute_next_run(self, automation: Automation) -> datetime:
        """Compute next run based on recurrence (e.g., next Monday)."""
        now = timezone.now()
        pattern = automation.recurrence_pattern
        config = automation.action_params.get("trigger", {}).get("config", {})

        if "weekly on Monday" in pattern:
            # Find next Monday
            days_ahead = (0 - now.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week if today is Monday
            next_run = now + timedelta(days=days_ahead)
            hour = int(config.get("time", "11:00").split(":")[0])
            return next_run.replace(hour=hour, minute=0, second=0, microsecond=0)
        # Extend for daily, etc.
        return now + timedelta(days=1)  # Fallback

    def _unschedule_automation(self, automation: Automation) -> None:
        deleted_count, _ = PeriodicTask.objects.filter(name=f"automation_{automation.id}").delete()
        if deleted_count > 0:
            logger.debug(f"Unscheduled {deleted_count} task(s) for automation {automation.id}")

    def _reschedule_automation(self, automation: Automation) -> None:
        self._unschedule_automation(automation)
        self._schedule_automation(automation)

    def _execute_workflow(self, automation: Automation, context: Dict[str, Any]) -> None:
        """
        Execute all actions defined in automation.action_params['actions'].
        Chains outputs via placeholders (e.g., {summary} from prior step).
        """
        action_params = automation.action_params or {}
        actions = action_params.get("actions", [])
        if not actions:
            logger.warning(f"No actions in workflow for automation {automation.id}")
            return

        logger.info(f"Executing workflow for automation {automation.id} with {len(actions)} actions")

        for idx, action in enumerate(actions, start=1):
            action_type = action.get("type")
            config = action.get("config", {})
            handler = self.action_registry.get(action_type)

            if not handler:
                logger.warning(f"No handler for action type '{action_type}' in automation {automation.id}")
                continue

            try:
                logger.info(f"Action {idx}/{len(actions)}: {action_type} | config: {config}")
                output = handler(config, context)
                if output:
                    context.update(output)  # Pipe to next actions
                logger.debug(f"Action {action_type} output: {output}")
            except Exception as e:
                logger.error(f"Failed to execute action '{action_type}': {e}")
                # Continue chain despite failure

    # ---------------- ACTION EXECUTORS ---------------- #
    def _execute_reminder(self, config: dict, context: dict) -> Optional[dict]:
        channel = config.get("channel", "default")
        logger.info(f"Sending reminder via {channel}")
        # TODO: Integrate with MessageService
        return {"reminder_sent": True}

    def _execute_extract_fields(self, config: dict, context: dict) -> Optional[dict]:
        fields = config.get("fields", [])
        text = context.get("text", "")
        extracted = {field: text for field in fields}  # Simple placeholder; use NER/LLM
        return extracted

    def _execute_append_google_sheet(self, config: dict, context: dict) -> Optional[dict]:
        spreadsheet_name = config.get("spreadsheet_name")
        columns = config.get("columns", [])
        row_data = {col: context.get(col, "") for col in columns}
        logger.info(f"Appending to Google Sheet '{spreadsheet_name}': {row_data}")
        # TODO: Google Sheets API
        return {"sheet_row_id": "123"}  # Placeholder

    def _execute_send_whatsapp_message(self, config: dict, context: dict) -> Optional[dict]:
        receiver_name = config.get("receiver_name")
        msg_template = config.get("message_template", "")
        # Resolve placeholders
        for k, v in context.items():
            msg_template = msg_template.replace(f"{{{{{k}}}}}", str(v))
        logger.info(f"Sending WhatsApp to {receiver_name}: {msg_template}")
        # TODO: WhatsApp API via MessageService
        return {"whatsapp_sent": True, "message": msg_template}

    def _execute_fetch_calendar_events(self, config: dict, context: dict) -> Optional[dict]:
        calendar_id = config.get("calendar_id", "primary")
        date = config.get("date")
        logger.info(f"Fetching events from calendar '{calendar_id}' on {date}")
        # TODO: Google Calendar API
        return {"event_list": ["Event 1", "Event 2"]}  # Placeholder

    def _execute_append_notion_page(self, config: dict, context: dict) -> Optional[dict]:
        database_name = config.get("database_name")
        fields_mapping = config.get("fields_mapping", {})
        row_data = {k: context.get(v, "") for k, v in fields_mapping.items()}
        logger.info(f"Appending to Notion '{database_name}': {row_data}")
        # TODO: Notion API
        return {"notion_page_id": "abc123"}

    def _execute_fetch_unread_emails(self, config: dict, context: dict) -> Optional[dict]:
        label = config.get("label", "inbox")
        filter_ = config.get("filter", "unread")
        limit = config.get("limit", 50)
        logger.info(f"Fetching {limit} {filter_} emails from {label}")
        # TODO: Gmail API via MessageService
        return {"fetched_emails": ["Email 1 body", "Email 2 body"]}

    def _execute_summarize_messages(self, config: dict, context: dict) -> Optional[dict]:
        input_data = config.get("input", context.get("fetched_data", []))
        style = config.get("style", "concise")
        logger.info(f"Summarizing {len(input_data)} messages ({style})")
        # TODO: LLM summarization
        summary = f"Summary of {len(input_data)} items: Key points here."
        return {"summary": summary}

    def _execute_create_calendar_event(self, config: dict, context: dict) -> Optional[dict]:
        event_title = config.get("event_title")
        time = config.get("time")
        duration = config.get("duration", 60)
        calendar_id = config.get("calendar_id", "primary")
        logger.info(f"Creating calendar event '{event_title}' at {time} ({duration} min)")
        # TODO: CalendarService
        return {"event_id": "evt456"}

    def _execute_send_email(self, config: dict, context: dict) -> Optional[dict]:
        receiver = config.get("receiver")
        subject = config.get("subject")
        body_template = config.get("body", "")
        # Resolve placeholders
        for k, v in context.items():
            body_template = body_template.replace(f"{{{{{k}}}}}", str(v))
        logger.info(f"Sending email to {receiver}: {subject}")
        # TODO: MessageService
        return {"email_sent": True, "body": body_template}

    def _execute_fetch_last_week_reports(self, config: dict, context: dict) -> Optional[dict]:
        timeframe = config.get("timeframe", "last_week")
        source = config.get("source", "reports")
        logger.info(f"Fetching {timeframe} {source}")
        # TODO: Query emails/docs
        return {"fetched_reports": ["Report 1", "Report 2"]}