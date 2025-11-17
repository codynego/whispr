from typing import List, Dict, Any, Optional
import openai
import json
import dateparser
from django.contrib.auth import get_user_model
from assistant.models import AssistantMessage
from datetime import datetime
from .models import KnowledgeVaultEntry

User = get_user_model()


def serialize_vault_context(vault_context):
    """
    Convert KnowledgeVaultEntry or list of entries to JSON-serializable dict(s).
    """
    if vault_context is None:
        return None
    if isinstance(vault_context, KnowledgeVaultEntry):
        return {
            "id": vault_context.id,
            "summary": vault_context.summary,
            "entities": vault_context.entities,
            "preferences": vault_context.preferences,
            "timestamp": vault_context.timestamp.isoformat() if vault_context.timestamp else None
        }
    if isinstance(vault_context, (list, tuple)):
        return [serialize_vault_context(e) for e in vault_context]
    return vault_context


class TaskPlanner:
    """
    Converts natural language into structured tasks.
    Now supports context-aware planning using previous messages.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", history_limit: int = 2):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.history_limit = history_limit

    def plan_tasks(
        self,
        user: User,
        user_message: str,
        vault_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert user natural language into structured action steps,
        using previous messages and optional vault context.
        """
        # 1️⃣ Previous conversation history
        history_msgs = AssistantMessage.objects.filter(user=user).order_by("-created_at")[:self.history_limit]
        history_msgs = reversed(history_msgs)
        conversation_history = ""
        for msg in history_msgs:
            role = "User" if msg.role == "user" else "Assistant"
            conversation_history += f"{role}: {msg.content}\n"

        # 2️⃣ Append vault context if available
        if vault_context:
            vault_context_serializable = serialize_vault_context(vault_context)
            conversation_history += f"\nVault context:\n{json.dumps(vault_context_serializable, indent=2)}\n"


        # 3️⃣ Call LLM
        raw_actions = self._call_llm(user_message, conversation_history)

        # 4️⃣ Normalize actions
        cleaned_actions = self._normalize_actions(raw_actions)
        return cleaned_actions


    def _call_llm(self, user_message: str, conversation_history: str, retry: int = 0) -> List[Dict[str, Any]]:
        today = datetime.now().date()
        prompt = (
            "You are an AI Task Planner for Whisone.\n\n"

            "Conversation so far:\n"
            + conversation_history
            + f"\n\nToday's date: {today}\n\n"

            "User's new message:\n\"\"\"" + user_message + "\"\"\"\n\n"

            "Your job:\n"
            "1. Extract all actionable tasks (notes, reminders, todos, calendar events, emails).\n"
            "2. Break multi-step instructions into separate actions.\n"
            "3. Identify intent clearly.\n"
            "4. Parse date/time expressions into ISO8601 format (YYYY-MM-DDTHH:MM).\n"
            "   - If no date is given, assume today.\n"
            "5. Include a confidence score (0–1).\n"
            "6. ALWAYS return a valid JSON array of task objects.\n"
            "7. NEVER include explanations, text, or code blocks — ONLY JSON.\n\n"

            "Rules:\n"
            "- Dates must be ISO8601.\n"
            "- Return ONLY a JSON array.\n"
            "- If the user is searching emails/events/notes/todos/reminders, extract FILTERS as a list of dictionaries, e.g. [{\"from\": \"example@example.com\"}, ...].\n"
            "- Do NOT write explanations.\n\n"

            "Action Mapping:\n"
            "- Notes: create_note, update_note, delete_note, fetch_notes\n"
            "   * Required field for create/update: 'content' (string)\n"
            "- Reminders: create_reminder, update_reminder, delete_reminder, fetch_reminders\n"
            "   * Required for create/update: 'text' (string), 'remind_at' (ISO8601 datetime)\n"
            "- Todos: create_todo, update_todo, delete_todo, fetch_todos\n"
            "   * Required for create/update: 'task' (string), 'done' (boolean optional for update)\n"
            "- Calendar: create_event, update_event, delete_event, fetch_events\n"
            "- Emails: fetch_emails, mark_email_read, send_email\n\n"

            "If the user wants to add a note/reminder/todo and no existing item is referenced, use create_* actions.\n"
            "Use update_* only if a specific item ID is referenced.\n\n"

            "Supported actions and schema examples:\n"
            "[\n"
            "  {\"action\": \"create_note\", \"params\": {\"content\": \"Buy milk\", \"service\": \"notes\"}, \"intent\": \"Create a note to buy milk\", \"confidence\": 0.9},\n"
            "  {\"action\": \"create_reminder\", \"params\": {\"text\": \"Attend meeting\", \"remind_at\": \"2025-11-17T14:00\", \"service\": \"calendar\"}, \"intent\": \"Set a reminder to attend meeting\", \"confidence\": 0.95},\n"
            "  {\"action\": \"create_todo\", \"params\": {\"task\": \"Finish report\", \"service\": \"todos\"}, \"intent\": \"Create a todo to finish report\", \"confidence\": 0.9},\n"
            "  {\"action\": \"fetch_events\", \"params\": {\"time_min\": \"2025-11-17T00:00\", \"time_max\": \"2025-11-17T23:59\", \"service\": \"calendar\"}, \"intent\": \"Get today's calendar events\", \"confidence\": 0.85},\n"
            "  {\"action\": \"fetch_emails\", \"params\": {\"filters\": [{\"from\": \"boss@example.com\"}], \"max_results\": 10}, \"intent\": \"Check emails from my boss\", \"confidence\": 0.9}\n"
            "]\n\n"

            "Always return JSON in this exact format with proper field names so TaskFrameBuilder can validate 'ready' status.\n"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You convert natural language to structured JSON tasks."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        content = response.choices[0].message.content

        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            if retry < 2:
                return self._retry_fix_json(content, user_message, conversation_history, retry)
            return []


    def _retry_fix_json(self, bad_output: str, original_message: str, conversation_history: str, retry: int) -> List[Dict[str, Any]]:
        today = datetime.now().date()
        repair_prompt = f"""
The previous response was INVALID JSON:
\"\"\"{bad_output}\"\"\"

today's date is {today}.

Fix it. Return ONLY a valid JSON array of actions based on:

Conversation:
{conversation_history}

User message:
\"\"\"{original_message}\"\"\"
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Fix invalid JSON and return clean JSON only."},
                {"role": "user", "content": repair_prompt}
            ],
            temperature=0
        )

        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except:
            return []


    # -------------------------
    # INTERNAL: Normalize actions
    # -------------------------
    # -------------------------
    # task_planner.py
    # -------------------------
    # (Modified normalization to match TaskFrame naming)

    def _normalize_actions(self, actions: List[Any]) -> List[Dict[str, Any]]:
        """
        - Ensures fields exist
        - Fix missing datetime via natural language parsing
        - Renames params to match TaskFrame required_fields
        - Adds confidence if missing
        """
        cleaned = []
        if not isinstance(actions, list):
            return cleaned

        param_mapping = {
            "create_reminder": {"datetime": "remind_at", "title": "text"},
            "update_reminder": {"datetime": "remind_at", "title": "text"},
            "create_event": {"datetime": "start_time"},
            "update_event": {"datetime": "start_time"}
        }

        for task in actions:
            if not isinstance(task, dict):
                continue

            action_name = task.get("action")
            params = task.get("params", {})
            intent = task.get("intent", action_name)
            confidence = float(task.get("confidence", 0.90))

            # -------- Date normalization --------
            if "datetime" in params and params["datetime"]:
                params["datetime"] = self._normalize_datetime(params["datetime"])

            # -------- Map param names to TaskFrame --------
            if action_name in param_mapping:
                for old_key, new_key in param_mapping[action_name].items():
                    if old_key in params and new_key not in params:
                        params[new_key] = params.pop(old_key)

            # -------- Basic service routing hint --------
            if "service" not in params:
                params["service"] = self._infer_service(action_name)

            cleaned.append({
                "action": action_name,
                "params": params,
                "intent": intent,
                "confidence": confidence
            })

        return cleaned



    # -------------------------
    # Parse natural datetime
    # -------------------------
    def _normalize_datetime(self, dt_str: str) -> Optional[str]:
        """
        Convert human language date/time into ISO-8601.
        Uses dateparser with current reference date to avoid wrong years.
        """
        result = dateparser.parse(
            dt_str,
            settings={'RELATIVE_BASE': datetime.now()}
        )
        if result:
            return result.isoformat()
        return None

    # -------------------------
    # Map action → default integration
    # -------------------------
    def _infer_service(self, action: str) -> str:
        if "email" in action:
            return "gmail"
        if "event" in action:
            return "calendar"
        if "note" in action:
            return "notes"
        if "reminder" in action:
            return "whatsapp"  # your default reminder channel
        if "todo" in action:
            return "todo"
        return "system"