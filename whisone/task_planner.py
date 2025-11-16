from typing import List, Dict, Any, Optional
import openai
import json
import dateparser
from django.contrib.auth import get_user_model
from assistant.models import AssistantMessage
from datetime import datetime

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
            "1. Extract all tasks (notes, reminders, todos, calendar events).\n"
            "2. Break multi-step instructions into separate actions.\n"
            "3. Identify intent clearly.\n"
            "4. Parse date/time expressions into ISO format (YYYY-MM-DDTHH:MM).\n"
            "   - If no date is given, assume today.\n"
            "5. Include a confidence score (0–1).\n"
            "6. ALWAYS return a valid JSON array.\n"
            "7. NEVER include explanations, text, or code blocks — ONLY JSON.\n\n"

            "Rules:\n"
            "- Dates must be ISO8601.\n"
            "- Return ONLY a JSON array.\n"
            "- If the user is searching emails/events/notes/todos/reminders, extract FILTER -  as a list of dictionary e.g [{sender: \"example@example.com\", from: \"example@example.com\"} etc].\n"
            "- Do NOT write explanations.\n\n"
            "- If the user wants to 'add' something but no specific note/reminder/todo exists, "
            "use create_note/create_reminder/create_todo.\n"
            "- Use update_* only if a specific note/reminder/todo or event_id is referenced.\n"
            "- For calendar events, use fetch_events/create_event/update_event/delete_event with the schema below.\n\n"

            "Supported actions:\n"
            "["
            "\"create_note\",\"update_note\",\"delete_note\","
            "\"create_reminder\",\"update_reminder\",\"delete_reminder\","
            "\"add_todo\",\"update_todo\",\"delete_todo\","
            "\"create_event\",\"update_event\",\"delete_event\",\"fetch_events\","
            "\"fetch_emails\",\"mark_email_read\",\"send_email\""
            "]\n\n"

            "CALENDAR ACTION SCHEMA:\n"
            "- create_event params:\n"
            "  {\"summary\": \"string\", \"description\": \"optional string\", "
            "\"start_time\": \"ISO8601\", \"end_time\": \"optional ISO8601\", "
            "\"attendees\": [\"email\"], \"timezone\": \"optional string\", "
            "\"service\": \"calendar\"}\n"
            "- update_event params:\n"
            "  {\"event_id\": \"string\", \"summary\": \"optional\", \"description\": \"optional\", "
            "\"start_time\": \"optional ISO8601\", \"end_time\": \"optional ISO8601\", "
            "\"attendees\": [\"email\"], \"service\": \"calendar\"}\n"
            "- delete_event params:\n"
            "  {\"event_id\": \"string\", \"service\": \"calendar\"}\n"
            "- fetch_events params:\n"
            "  {\"time_min\": \"optional ISO8601\", \"time_max\": \"optional ISO8601\", "
            "\"max_results\": 10, \"service\": \"calendar\"}\n\n"

            "JSON ACTION SCHEMA EXAMPLE:\n"
            "[{\"action\": \"create_reminder\","
            "\"params\": {\"title\": \"Buy milk\", \"datetime\": \"2025-11-15T18:00\", \"service\": \"calendar\"},"
            "\"intent\": \"Set a reminder to buy milk\","
            "\"confidence\": 0.90}]\n"
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
    def _normalize_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        - Ensures fields exist
        - Fix missing datetime via natural language parsing
        - Adds confidence if missing
        """

        cleaned = []

        for task in actions:
            action_name = task.get("action")
            params = task.get("params", {})
            intent = task.get("intent", action_name)
            confidence = float(task.get("confidence", 0.90))

            # -------- Date normalization --------
            if "datetime" in params and params["datetime"]:
                params["datetime"] = self._normalize_datetime(params["datetime"])

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