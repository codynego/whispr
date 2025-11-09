# assistant/services/automation_service.py
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jsonschema
from django.utils import timezone as dj_timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django_celery_beat.models import PeriodicTask, ClockedSchedule, CrontabSchedule
from unified.utils.calendar_utils import create_calendar_event

from assistant.models import Automation

logger = logging.getLogger(__name__)


class AutomationService:
    """
    Enterprise-grade automation engine with:
    • Multi-step workflows
    • Timezone-aware scheduling
    • JSONSchema validation
    • Global templating with {{{mustache}}} syntax
    • Real email + WhatsApp integration
    • Daily, weekly, monthly, and weekday recurrence support
    • Audit-ready logging
    """

    # -------------------------------------------------------------------------
    # JSONSchema for workflow validation
    # -------------------------------------------------------------------------
    WORKFLOW_SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "trigger": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["on_schedule"]},
                    "config": {"type": "object"}
                }
            },
            "actions": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["type", "config"],
                    "properties": {
                        "type": {"type": "string"},
                        "config": {"type": "object"}
                    },
                    "additionalProperties": False
                }
            }
        },
        "required": ["actions"],
        "additionalProperties": False
    }

    def __init__(self, user):
        self.user = user
        self.action_registry = self._register_actions()

    # -------------------------------------------------------------------------
    # ACTION REGISTRY
    # -------------------------------------------------------------------------
    def _register_actions(self) -> Dict[str, Callable]:
        """Register all available action handlers."""
        return {
            "reminder": self._execute_reminder,
            "extract_fields": self._execute_extract_fields,
            "append_google_sheet": self._execute_append_google_sheet,
            "send_whatsapp_message": self._execute_send_whatsapp_message,
            "fetch_calendar_events": self._execute_fetch_calendar_events,
            "append_notion_page": self._execute_append_notion_page,
            "fetch_unread_emails": self._execute_fetch_unread_emails,
            "summarize_messages": self._execute_summarize_messages,
            "create_calendar_event": self._execute_create_calendar_event,
            "send_email": self._execute_send_email,
            "fetch_last_week_reports": self._execute_fetch_last_week_reports,
        }

    # -------------------------------------------------------------------------
    # WORKFLOW VALIDATION
    # -------------------------------------------------------------------------
    def _validate_workflow(self, workflow: dict) -> None:
        """Validate workflow against schema."""
        jsonschema.validate(workflow, self.WORKFLOW_SCHEMA)

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------
    def create_automation(
        self,
        name: str,
        workflow: dict,
        trigger_type: str = "on_schedule",
        next_run_at: Optional[datetime] = None,
        recurrence_pattern: Optional[str] = None,
        description: Optional[str] = None,
        is_active: bool = True,
        trigger_condition: Optional[dict] = None,
    ) -> Optional[Automation]:
        """Create a new automation with validation and scheduling."""
        try:
            logger.info(f"[{self.user.first_name}] Creating automation: {name}")

            # 1. Validate workflow structure
            self._validate_workflow(workflow)

            # 2. Parse and validate next_run_at with timezone awareness
            next_run_at = self._parse_next_run_at(next_run_at, workflow)

            # 3. Merge trigger configuration
            action_params = workflow.copy()
            if trigger_condition:
                if "trigger" not in action_params:
                    action_params["trigger"] = {}
                if "config" not in action_params["trigger"]:
                    action_params["trigger"]["config"] = {}
                action_params["trigger"]["config"].update(trigger_condition)

            # 4. Create automation instance
            automation = Automation.objects.create(
                user=self.user,
                name=name,
                description=description or "",
                action_params=action_params,
                trigger_type=trigger_type,
                next_run_at=next_run_at,
                recurrence_pattern=recurrence_pattern or "",
                is_active=is_active,
            )

            # 5. Schedule if active and scheduled trigger
            if trigger_type == "on_schedule" and is_active:
                self._schedule_automation(automation)

            logger.info(f"Automation {automation.id} created successfully")
            return automation

        except jsonschema.ValidationError as e:
            logger.error(f"Workflow validation failed: {e.message}")
            return None
        except ValueError as e:
            logger.error(f"Value error in automation creation: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error creating automation: {e}")
            return None

    def update_automation(
        self, 
        automation_id: int, 
        **updates
    ) -> Optional[Automation]:
        """Update an existing automation with rescheduling if needed."""
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)

            # Handle workflow update with validation
            if "workflow" in updates:
                new_workflow = updates.pop("workflow")
                self._validate_workflow(new_workflow)
                # Merge with existing params to preserve trigger config
                merged_params = automation.action_params.copy()
                merged_params.update(new_workflow)
                updates["action_params"] = merged_params

            # Handle next_run_at parsing
            if "next_run_at" in updates:
                action_params = updates.get("action_params", automation.action_params)
                updates["next_run_at"] = self._parse_next_run_at(
                    updates["next_run_at"], 
                    action_params
                )

            # Update allowed fields only
            allowed_fields = {f.name for f in Automation._meta.fields}
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(automation, field, value)

            automation.save()

            # Reschedule if schedule-related fields changed
            schedule_fields = {
                "next_run_at", "recurrence_pattern", 
                "trigger_type", "is_active", "action_params"
            }
            if any(k in updates for k in schedule_fields):
                if automation.trigger_type == "on_schedule" and automation.is_active:
                    self._reschedule_automation(automation)
                else:
                    self._unschedule_automation(automation)

            logger.info(f"Automation {automation_id} updated successfully")
            return automation

        except Automation.DoesNotExist:
            logger.error(f"Automation {automation_id} not found for user {self.user.first_name}")
            return None
        except Exception as e:
            logger.exception(f"Error updating automation {automation_id}: {e}")
            return None

    def delete_automation(self, automation_id: int) -> bool:
        """Delete an automation and unschedule it."""
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)
            self._unschedule_automation(automation)
            automation.delete()
            logger.info(f"Automation {automation_id} deleted successfully")
            return True
        except Automation.DoesNotExist:
            logger.error(f"Automation {automation_id} not found")
            return False
        except Exception as e:
            logger.exception(f"Error deleting automation {automation_id}: {e}")
            return False

    def trigger_automation(
        self, 
        automation_id: int, 
        context: Optional[dict] = None
    ) -> bool:
        """Manually trigger an automation with optional context."""
        try:
            automation = Automation.objects.get(id=automation_id, user=self.user)

            # Check if automation should trigger based on conditions
            if not automation.should_trigger(context):
                logger.debug(f"Automation {automation_id} skipped – conditions not met")
                return False

            # Build execution context
            trigger_context = {
                **(context or {}),
                "trigger_time": dj_timezone.now(),
                "trigger_type": "manual",
                "automation_name": automation.name,
                "automation_id": automation.id,
                "user_id": self.user.id,
            }

            # Execute workflow
            self._execute_workflow(automation, trigger_context)

            # Update last triggered timestamp
            automation.last_triggered_at = dj_timezone.now()
            automation.save(update_fields=["last_triggered_at"])

            # Compute and schedule next run for recurring automations
            if automation.recurrence_pattern and automation.trigger_type == "on_schedule":
                automation.next_run_at = self._compute_next_run(automation)
                automation.save(update_fields=["next_run_at"])
                self._reschedule_automation(automation)

            logger.info(f"Automation {automation_id} triggered successfully")
            return True

        except Automation.DoesNotExist:
            logger.error(f"Automation {automation_id} not found")
            return False
        except Exception as e:
            logger.exception(f"Trigger failed for automation {automation_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # SCHEDULING WITH TIMEZONE SUPPORT
    # -------------------------------------------------------------------------
    def _schedule_automation(self, automation: Automation) -> None:
        """Schedule an automation using django-celery-beat."""
        if not automation.next_run_at:
            logger.warning(f"No next_run_at for automation {automation.id}, skipping schedule")
            return

        # Remove any existing schedule
        self._unschedule_automation(automation)

        task_name = f"automation_{automation.id}"
        args = json.dumps([automation.id])
        config = automation.action_params.get("trigger", {}).get("config", {})

        try:
            if automation.recurrence_pattern:
                # Create cron schedule for recurring automations
                cron_expr = self._pattern_to_cron(automation.recurrence_pattern, config)
                if cron_expr:
                    minute, hour, day, month, day_of_week = cron_expr.split()
                    schedule, _ = CrontabSchedule.objects.get_or_create(
                        minute=minute,
                        hour=hour,
                        day_of_month=day,
                        month_of_year=month,
                        day_of_week=day_of_week,
                    )
                    PeriodicTask.objects.create(
                        crontab=schedule,
                        name=task_name,
                        task="assistant.tasks.execute_automation",
                        args=args,
                        enabled=True,
                    )
                    logger.info(f"Scheduled recurring automation {automation.id} with cron: {cron_expr}")
                else:
                    logger.warning(f"Unsupported recurrence pattern: {automation.recurrence_pattern}")
            else:
                # Create one-off clocked schedule
                clocked, _ = ClockedSchedule.objects.get_or_create(
                    clocked_time=automation.next_run_at
                )
                PeriodicTask.objects.create(
                    clocked=clocked,
                    name=task_name,
                    task="assistant.tasks.execute_automation",
                    args=args,
                    one_off=True,
                    enabled=True,
                )
                logger.info(f"Scheduled one-off automation {automation.id} at {automation.next_run_at}")

        except Exception as e:
            logger.exception(f"Error scheduling automation {automation.id}: {e}")

    def _pattern_to_cron(self, pattern: str, config: dict) -> Optional[str]:
        """Convert recurrence pattern to cron expression."""
        time_str = config.get("time", "09:00")
        try:
            hour, minute = map(int, time_str.split(":"))
        except (ValueError, AttributeError):
            hour, minute = 9, 0

        pattern_lower = pattern.lower().strip()
        
        # Cron format: minute hour day month day_of_week
        patterns = {
            "daily": f"{minute} {hour} * * *",
            "daily on weekdays": f"{minute} {hour} * * 1-5",
            "weekly on monday": f"{minute} {hour} * * 1",
            "weekly on tuesday": f"{minute} {hour} * * 2",
            "weekly on wednesday": f"{minute} {hour} * * 3",
            "weekly on thursday": f"{minute} {hour} * * 4",
            "weekly on friday": f"{minute} {hour} * * 5",
            "weekly on saturday": f"{minute} {hour} * * 6",
            "weekly on sunday": f"{minute} {hour} * * 0",
            "monthly": f"{minute} {hour} 1 * *",  # First day of the month
        }
        
        return patterns.get(pattern_lower)

    def _compute_next_run(self, automation: Automation) -> datetime:
        """Compute next run time for recurring automations."""
        now = dj_timezone.now()
        pattern = (automation.recurrence_pattern or "").lower().strip()
        config = automation.action_params.get("trigger", {}).get("config", {})
        
        # Get timezone
        tz_str = config.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_str)
        except ZoneInfoNotFoundError:
            logger.warning(f"Invalid timezone {tz_str}, using UTC")
            tz = ZoneInfo("UTC")

        # Get time
        time_str = config.get("time", "09:00")
        try:
            hour, minute = map(int, time_str.split(":"))
        except (ValueError, AttributeError):
            hour, minute = 9, 0

        # Convert current time to target timezone
        now_tz = now.astimezone(tz)
        
        # Create base datetime for today at specified time
        next_run = now_tz.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If time has passed today, start from tomorrow
        if next_run <= now_tz:
            next_run += timedelta(days=1)

        # Handle weekday-specific patterns
        if "weekdays" in pattern:
            # Skip to next weekday (Mon-Fri)
            while next_run.weekday() >= 5:  # 5=Saturday, 6=Sunday
                next_run += timedelta(days=1)
        elif "monday" in pattern:
            while next_run.weekday() != 0:
                next_run += timedelta(days=1)
        elif "tuesday" in pattern:
            while next_run.weekday() != 1:
                next_run += timedelta(days=1)
        elif "wednesday" in pattern:
            while next_run.weekday() != 2:
                next_run += timedelta(days=1)
        elif "thursday" in pattern:
            while next_run.weekday() != 3:
                next_run += timedelta(days=1)
        elif "friday" in pattern:
            while next_run.weekday() != 4:
                next_run += timedelta(days=1)
        elif "saturday" in pattern:
            while next_run.weekday() != 5:
                next_run += timedelta(days=1)
        elif "sunday" in pattern:
            while next_run.weekday() != 6:
                next_run += timedelta(days=1)
        elif "monthly" in pattern:
            # Adjust to 1st of the month
            next_run = next_run.replace(day=1)
            if next_run <= now_tz:
                # Move to next month
                if next_run.month == 12:
                    next_run = next_run.replace(year=next_run.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=next_run.month + 1)

        # Convert back to default timezone
        return next_run.astimezone(dj_timezone.get_current_timezone())

    def _parse_next_run_at(
        self, 
        next_run_at_input: Optional[datetime], 
        workflow: dict
    ) -> Optional[datetime]:
        """Parse and validate next_run_at input."""
        if next_run_at_input is None:
            return self._compute_next_run_from_workflow(workflow)
        
        # Ensure timezone awareness
        if isinstance(next_run_at_input, datetime):
            if dj_timezone.is_naive(next_run_at_input):
                return dj_timezone.make_aware(next_run_at_input)
            return next_run_at_input
        
        # Handle string input
        if isinstance(next_run_at_input, str):
            try:
                dt = datetime.fromisoformat(next_run_at_input)
                if dj_timezone.is_naive(dt):
                    return dj_timezone.make_aware(dt)
                return dt
            except ValueError:
                logger.error(f"Invalid datetime string: {next_run_at_input}")
                return self._compute_next_run_from_workflow(workflow)
        
        return None

    def _compute_next_run_from_workflow(self, workflow: dict) -> datetime:
        """Compute next run time from workflow trigger config."""
        config = workflow.get("trigger", {}).get("config", {})
        
        tz_str = config.get("timezone", "UTC")
        try:
            tz = ZoneInfo(tz_str)
        except ZoneInfoNotFoundError:
            logger.warning(f"Invalid timezone {tz_str}, using UTC")
            tz = ZoneInfo("UTC")
        
        time_str = config.get("time", "09:00")
        try:
            hour, minute = map(int, time_str.split(":"))
        except (ValueError, AttributeError):
            hour, minute = 9, 0
        
        now = dj_timezone.now().astimezone(tz)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if next_run <= now:
            next_run += timedelta(days=1)
        
        return next_run.astimezone(dj_timezone.get_current_timezone())

    def _reschedule_automation(self, automation: Automation) -> None:
        """Reschedule an automation by removing and recreating its schedule."""
        self._unschedule_automation(automation)
        self._schedule_automation(automation)

    def _unschedule_automation(self, automation: Automation) -> None:
        """Remove all scheduled tasks for an automation."""
        task_name = f"automation_{automation.id}"
        deleted_count, _ = PeriodicTask.objects.filter(name=task_name).delete()
        if deleted_count > 0:
            logger.info(f"Unscheduled automation {automation.id} ({deleted_count} tasks removed)")

    # -------------------------------------------------------------------------
    # EXECUTION ENGINE
    # -------------------------------------------------------------------------
    def _execute_workflow(
        self, 
        automation: Automation, 
        context: Dict[str, Any]
    ) -> None:
        """Execute all actions in a workflow sequentially."""
        actions = automation.action_params.get("actions", [])
        logger.info(f"Executing {len(actions)} action(s) for automation '{automation.name}'")

        for idx, action in enumerate(actions, 1):
            action_type = action.get("type")
            config = action.get("config", {})
            handler = self.action_registry.get(action_type)

            if not handler:
                logger.warning(f"Unknown action type '{action_type}' in automation {automation.id}")
                continue

            try:
                logger.info(f"  [{idx}/{len(actions)}] Executing {action_type}")
                output = handler(config, context.copy())
                
                # Merge action output into context for subsequent actions
                if output and isinstance(output, dict):
                    context.update(output)
                    
            except Exception as e:
                logger.error(
                    f"Action '{action_type}' failed in automation {automation.id}: {e}", 
                    exc_info=True
                )
                # Continue with remaining actions unless critical failure

    # -------------------------------------------------------------------------
    # TEMPLATING ENGINE
    # -------------------------------------------------------------------------
    def _resolve_placeholders(self, template: str, context: Dict[str, Any]) -> str:
        """Replace {{{placeholders}}} with context values."""
        if not template or not isinstance(template, str):
            return template or ""
        
        resolved = template
        for key, value in context.items():
            placeholder = f"{{{{{{{key}}}}}}}"
            if placeholder in resolved:
                # Convert value to string, handling None
                str_value = "" if value is None else str(value)
                resolved = resolved.replace(placeholder, str_value)
        
        return resolved

    # -------------------------------------------------------------------------
    # STUB ACTION HANDLERS (TODO: Implement fully)
    # -------------------------------------------------------------------------
    def _execute_extract_fields(self, config: dict, context: dict) -> Optional[dict]:
        logger.warning("Action 'extract_fields' not implemented yet")
        return None

    def _execute_append_google_sheet(self, config: dict, context: dict) -> Optional[dict]:
        logger.warning("Action 'append_google_sheet' not implemented yet")
        return None

    def _execute_fetch_calendar_events(self, config: dict, context: dict) -> Optional[dict]:
        logger.warning("Action 'fetch_calendar_events' not implemented yet")
        return None

    def _execute_append_notion_page(self, config: dict, context: dict) -> Optional[dict]:
        logger.warning("Action 'append_notion_page' not implemented yet")
        return None

    def _execute_fetch_unread_emails(self, config: dict, context: dict) -> Optional[dict]:
        logger.warning("Action 'fetch_unread_emails' not implemented yet")
        return None

    def _execute_summarize_messages(self, config: dict, context: dict) -> Optional[dict]:
        logger.warning("Action 'summarize_messages' not implemented yet")
        return None

    def _execute_fetch_last_week_reports(self, config: dict, context: dict) -> Optional[dict]:
        logger.warning("Action 'fetch_last_week_reports' not implemented yet")
        return None

    # -------------------------------------------------------------------------
    # ACTION HANDLERS
    # -------------------------------------------------------------------------
    def _execute_send_email(self, config: dict, context: dict) -> Optional[dict]:
        """Send email via Gmail API with optional AI-generated content."""
        receiver = self._resolve_placeholders(config.get("receiver", ""), context)
        subject_template = config.get("subject", "")
        body_template = config.get("body", "")
        body_html = self._resolve_placeholders(config.get("body_html", ""), context)
        thread_id = config.get("thread_id")
        attachments = config.get("attachments", [])

        # Fallback receiver
        if not receiver:
            receiver = getattr(self.user, 'manager_email', None) or self.user.email
            if not receiver:
                logger.error("No email receiver specified and no fallback available")
                return None

        # Resolve templates
        subject = self._resolve_placeholders(subject_template, context) if subject_template else None
        body = self._resolve_placeholders(body_template, context) if body_template else None

        # Generate missing content if needed
        if not subject or not body:
            generated = self._generate_email_content(receiver, subject or "", body or "", context)
            subject = subject or generated.get("subject", "No Subject")
            body = body or generated.get("body", "No body generated.")

        # Get Gmail account
        try:
            gmail_account = self.user.channel_accounts.filter(channel='gmail').first()
            if not gmail_account:
                logger.error(f"No Gmail account linked for user {self.user.first_name}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch Gmail account: {e}")
            return None

        # Queue email via Celery
        try:
            from unified.utils.email_utils import send_gmail_email
            result = send_gmail_email.delay(
                account_id=gmail_account.id,
                to_email=receiver,
                subject=subject,
                body=body,
                body_html=body_html,
                attachments=attachments,
                thread_id=thread_id,
            )

            logger.info(f"📧 Queued Gmail to {receiver}: {subject} (task: {result.id})")
            return {
                "email_queued": True,
                "task_id": str(result.id),
                "receiver": receiver,
                "subject": subject,
                "body_preview": body[:100] + "..." if len(body) > 100 else body,
            }
        except Exception as e:
            logger.error(f"Failed to queue email: {e}")
            return None

    def _generate_email_content(
        self, 
        receiver: str, 
        subject_fallback: str, 
        body_fallback: str, 
        context: dict
    ) -> dict:
        """Generate email content using AI (Gemini or fallback)."""
        try:
            import google.generativeai as genai
            
            # Configure API
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')

            # Serialize context data safely
            serializable_context = {
                k: v for k, v in context.items() 
                if k in ['summary', 'fetched_emails', 'ai_summary', 'event_title']
            }
            context_json = json.dumps(serializable_context, default=str, indent=2)

            # Build context-aware prompt
            prompt = f"""
Generate a professional email for {self.user.get_full_name() or self.user.first_name} to send to {receiver}.

Automation context:
- Name: {context.get('automation_name', 'Unnamed')}
- Trigger: {context.get('trigger_type', 'scheduled')}
- Data: {context_json}

Requirements:
- If subject is missing, create a concise, engaging one (max 60 chars)
- If body is missing, write a polite, professional 3-5 sentence message
- Output ONLY valid JSON: {{"subject": "Your Subject", "body": "Your Body"}}
"""

            response = model.generate_content(prompt)
            generated_text = response.text.strip()

            # Parse JSON response
            # Remove markdown code blocks if present
            if generated_text.startswith("```json"):
                generated_text = generated_text[7:]
            if generated_text.startswith("```"):
                generated_text = generated_text[3:]
            if generated_text.endswith("```"):
                generated_text = generated_text[:-3]
            generated_text = generated_text.strip()
            
            generated = json.loads(generated_text)
            return {
                "subject": generated.get("subject", subject_fallback or "Update"),
                "body": generated.get("body", body_fallback or "Please review."),
            }

        except ImportError:
            logger.warning("google-generativeai not installed; using fallback")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini JSON response: {e}")
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")

        # Fallback
        return {
            "subject": subject_fallback or f"Update from {self.user.get_full_name() or self.user.first_name}",
            "body": body_fallback or "Hi, this is an automated message. Please check your dashboard for details.",
        }

    def _execute_send_whatsapp_message(
        self, 
        config: dict, 
        context: dict
    ) -> Optional[dict]:
        """Send WhatsApp message via Cloud API."""
        receiver_number_placeholder = config.get("receiver_number", "")
        receiver_number = self._resolve_placeholders(receiver_number_placeholder, context) or getattr(self.user, 'whatsapp', None)
        receiver_name_placeholder = config.get("receiver_name", "")
        receiver_name = self._resolve_placeholders(receiver_name_placeholder, context) or self.user.get_full_name() or self.user.first_name
        message_template = config.get("message_template", "")
        message = self._resolve_placeholders(message_template, context)

        if not receiver_number or not message:
            logger.error("Missing WhatsApp receiver_number or message")
            return None

        # Create WhatsAppMessage record
        try:
            from whatsapp.models import WhatsAppMessage
            wa_message = WhatsAppMessage.objects.create(
                user=self.user,
                to_number=receiver_number,
                message=message,
                status='pending',
            )
        except ImportError:
            logger.error("WhatsApp models not available")
            return None
        except Exception as e:
            logger.error(f"Failed to create WhatsAppMessage: {e}")
            return None

        # Queue via Celery
        try:
            from whatsapp.tasks import send_whatsapp_message_task
            result = send_whatsapp_message_task.delay(wa_message.id)

            logger.info(
                f"📱 Queued WhatsApp to {receiver_name or receiver_number}: "
                f"{message[:50]}... (task: {result.id})"
            )
            return {
                "whatsapp_queued": True,
                "task_id": str(result.id),
                "message_id": wa_message.id,
                "receiver": receiver_number,
                "message_preview": message[:100] + "..." if len(message) > 100 else message,
            }
        except Exception as e:
            logger.error(f"Failed to queue WhatsApp message: {e}")
            return None

    def _execute_reminder(self, config: dict, context: dict) -> Optional[dict]:
        """Execute reminder via WhatsApp or Email."""
        channel = config.get("channel", "whatsapp").lower()
        message = self._resolve_placeholders(config.get("message", ""), context)
        title = self._resolve_placeholders(config.get("title", ""), context)

        # Generate message if missing
        if not message:
            generated = self._generate_reminder_content(title, context)
            message = generated.get("message", "Reminder: Action required!")

        if channel == "whatsapp":
            wa_config = {
                "receiver_number": self._resolve_placeholders(config.get("receiver_number", ""), context) or getattr(self.user, 'phone_number', None) or getattr(self.user, 'whatsapp', None),
                "receiver_name": self._resolve_placeholders(config.get("receiver_name", ""), context) or "You",
                "message_template": message,
            }
            if not wa_config["receiver_number"]:
                logger.error("No WhatsApp receiver number available")
                return None
            return self._execute_send_whatsapp_message(wa_config, context)

        elif channel == "email":
            email_config = {
                "receiver": self._resolve_placeholders(config.get("receiver", ""), context) or self.user.email,
                "subject": title or "Reminder",
                "body": message,
            }
            return self._execute_send_email(email_config, context)

        else:
            logger.info(f"🔔 Reminder '{title}' via {channel}: {message}")
            return {"reminder_sent": True, "channel": channel, "message": message}

    def _generate_reminder_content(self, title: str, context: dict) -> dict:
        """Generate reminder message content using AI."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')

            trigger_time_str = str(context.get('trigger_time', 'now'))

            prompt = f"""
    You're a friendly personal assistant reminding your user about something important. Craft a warm, natural reminder message (3-4 sentences) for: "{title}"

    Context: {title}  # Fallback to title if no description
    Triggered at: {trigger_time_str}

    Keep it casual and encouraging, like chatting with a close colleague—add a touch of empathy or motivation to make it feel personal (e.g., "Hey, just circling back on that chemistry session at 6pm—don't want you stressing over it, but let's get you prepped with those notes. You've got this, and I'm here if you need a quick summary."). Make sure it's urgent but supportive, building a bit more rapport.

    Output ONLY JSON: {{"message": "Your reminder text"}}
    """

            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean JSON
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            generated = json.loads(text.strip())
            return {"message": generated.get("message", "")}

        except Exception as e:
            logger.error(f"Reminder generation failed: {e}")
            return {"message": f"Reminder: {title} – Action required now!"}

    def _execute_create_calendar_event(self, config: dict, context: dict) -> Optional[dict]:
        summary = self._resolve_placeholders(config.get("event_title", ""), context)
        start_str = config.get("time")  # e.g., "2025-11-10T14:00:00"
        try:
            start_time = datetime.fromisoformat(start_str) if start_str else dj_timezone.now() + timedelta(hours=1)
        except ValueError:
            logger.warning(f"Invalid start time format: {start_str}, using default")
            start_time = dj_timezone.now() + timedelta(hours=1)
        
        # Ensure timezone awareness
        if dj_timezone.is_naive(start_time):
            start_time = dj_timezone.make_aware(start_time)
        
        duration = config.get("duration", 60)
        end_time = start_time + timedelta(minutes=duration)
        if dj_timezone.is_naive(end_time):
            end_time = dj_timezone.make_aware(end_time)
        
        # Get calendar account (assume 'calendar' channel)
        calendar_account = self.user.channel_accounts.filter(channel='calendar').first()
        if not calendar_account:
            logger.error("No Calendar account linked")
            return None

        # Queue creation
        result = create_calendar_event.delay(
            calendar_account.id, summary, start_time, end_time,
            description=config.get("description", ""),
            location=config.get("location", ""),
            attendees=config.get("attendees", []),
            all_day=config.get("all_day", False)
        )
        return {"event_queued": True, "task_id": result.id, "summary": summary}