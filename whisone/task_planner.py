from typing import List, Dict, Any, Optional
import openai
import json
import dateparser
from django.contrib.auth import get_user_model
from assistant.models import AssistantMessage
from datetime import datetime

User = get_user_model()

class TaskPlanner:
    """
    Converts natural language into structured tasks.
    Supports:
    - Context-aware planning using previous messages
    - Notes, reminders, todos, calendar events
    - Accurate date parsing relative to today
    """

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini", history_limit: int = 3):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.model = model
        self.history_limit = history_limit

    def plan_tasks(self, user: User, user_message: str) -> List[Dict[str, Any]]:
        # Retrieve recent conversation
        history_msgs = AssistantMessage.objects.filter(user=user).order_by("-created_at")[:self.history_limit]
        conversation_history = "\n".join(
            f"{'User' if msg.role=='user' else 'Assistant'}: {msg.content}" for msg in reversed(history_msgs)
        )

        # Call LLM with context
        raw_actions = self._call_llm(user_message, conversation_history)

        # Normalize actions (date, service mapping, confidence)
        return self._normalize_actions(raw_actions)

    def _call_llm(self, user_message: str, conversation_history: str, retry: int = 0) -> List[Dict[str, Any]]:
        today = datetime.now().date()
        prompt = f"""
You are an AI Task Planner for Whisone.

Conversation so far:
{conversation_history}

Today's date: {today}

User's new message:
\"\"\"{user_message}\"\"\"

Your job:
1. Extract all tasks (notes, reminders, todos, calendar events).
2. Break multi-step instructions into separate actions.
3. Identify intent clearly.
4. Parse date/time expressions into ISO format (YYYY-MM-DDTHH:MM).
   - If no date is given, assume today.
5. Include a confidence score (0–1).
6. ALWAYS return a valid JSON array.
7. NEVER include explanations, text, or code blocks — ONLY JSON.

Rules:
- If the user wants to "add" something but no specific note/reminder/todo exists, use create_note/create_reminder/create_todo.
- Use update_* only if a specific note/reminder/todo or event_id is referenced.
- For calendar events, use create_event/update_event/delete_event as needed.

Supported actions:
["create_note","update_note","delete_note",
 "create_reminder","update_reminder","delete_reminder",
 "add_todo","update_todo","delete_todo",
 "create_event","update_event","delete_event",
 "fetch_emails","mark_email_read","send_email"]

JSON Action Schema:
[{
    "action": "create_reminder",
    "params": {
        "title": "string",
        "datetime": "ISO8601",
        "recurrence": "optional",
        "service": "gmail|calendar|notes|todo|whatsapp|sms|system"
    },
    "intent": "short natural language summary",
    "confidence": 0.90
}]
"""
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

Today's date: {today}

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
        try:
            return json.loads(response.choices[0].message.content)
        except:
            return []

    def _normalize_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []

        for task in actions:
            action_name = task.get("action")
            params = task.get("params", {})
            intent = task.get("intent", action_name)
            confidence = float(task.get("confidence", 0.90))

            # Date normalization
            if "datetime" in params and params["datetime"]:
                params["datetime"] = self._normalize_datetime(params["datetime"])

            # Service inference
            if "service" not in params:
                params["service"] = self._infer_service(action_name)

            cleaned.append({
                "action": action_name,
                "params": params,
                "intent": intent,
                "confidence": confidence
            })

        return cleaned

    def _normalize_datetime(self, dt_str: str) -> Optional[str]:
        """
        Convert natural language date/time into ISO-8601 using today as reference.
        """
        result = dateparser.parse(dt_str, settings={'RELATIVE_BASE': datetime.now()})
        return result.isoformat() if result else None

    def _infer_service(self, action: str) -> str:
        if "email" in action:
            return "gmail"
        if "event" in action:
            return "calendar"
        if "note" in action:
            return "notes"
        if "reminder" in action:
            return "whatsapp"
        if "todo" in action:
            return "todo"
        return "system"
