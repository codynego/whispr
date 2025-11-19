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
    Converts user natural language into structured tasks or general queries.
    Uses conversation history for context to generate accurate and complete actions.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", history_limit: int = 3):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.history_limit = history_limit

    # -------------------------
    # Public interface
    # -------------------------
    def plan_tasks(self, user: User, user_message: str) -> List[Dict[str, Any]]:
        """
        Convert a user message into structured tasks or general queries.
        """
        conversation_history = self._get_conversation_history(user)
        raw_actions = self._call_llm(user_message, conversation_history)
        return self._normalize_actions(raw_actions)

    # -------------------------
    # Build conversation history
    # -------------------------
    def _get_conversation_history(self, user: User) -> str:
        messages = AssistantMessage.objects.filter(user=user).order_by("-created_at")[:self.history_limit]
        conversation = ""
        for msg in reversed(messages):
            role = "User" if msg.role == "user" else "Assistant"
            conversation += f"{role}: {msg.content}\n"
        return conversation

    # -------------------------
    # LLM interaction
    # -------------------------
    def _call_llm(self, user_message: str, conversation_history: str, retry: int = 0) -> List[Dict[str, Any]]:
        today = datetime.now().date()
        prompt = (
            "You are an AI Task Planner.\n\n"
            f"Conversation so far:\n{conversation_history}\n\n"
            f"Today's date: {today}\n\n"
            f"User's new message:\n\"\"\"{user_message}\"\"\"\n\n"
            "Your job:\n"
            "1. Extract actionable tasks (notes, reminders, todos, calendar events, emails).\n"
            "2. Identify general queries for knowledge retrieval.\n"
            "3. Break multi-step instructions into separate actions.\n"
            "4. Parse dates/times into ISO8601 format (YYYY-MM-DDTHH:MM).\n"
            "5. Include confidence score (0–1).\n"
            "6. Return ONLY a valid JSON array of actions; NO explanations.\n\n"
            "Action Mapping:\n"
            "- Notes: create_note, delete_note, fetch_notes\n"
            "- Reminders: create_reminder, delete_reminder, fetch_reminders\n"
            "- Todos: create_todo, delete_todo, fetch_todos\n"
            "- Calendar: create_event, update_event, delete_event, fetch_events\n"
            "- Emails: fetch_emails, mark_email_read, send_email\n"
            "- General Queries: general_query\n\n"
            "Return JSON array. Examples:\n"
            "[\n"
            "  {\"action\": \"create_note\", \"params\": {\"content\": \"Buy milk\"}, \"intent\": \"Create a note to buy milk\", \"confidence\": 0.9},\n"
            "  {\"action\": \"create_reminder\", \"params\": {\"text\": \"Attend meeting\", \"remind_at\": \"2025-11-17T14:00\"}, \"intent\": \"Set a reminder to attend meeting\", \"confidence\": 0.95},\n"
            "  {\"action\": \"general_query\", \"params\": {\"entity_type\": \"events\", \"topic\": \"meeting\", \"time_range\": {\"start\": \"2025-11-17T00:00\", \"end\": \"2025-11-23T23:59\"}}, \"intent\": \"Who did I meet this week?\", \"confidence\": 0.95}\n"
            "]"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Convert natural language into structured JSON tasks or queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            content = response.choices[0].message.content
            return json.loads(content) if isinstance(json.loads(content), list) else []
        except (json.JSONDecodeError, KeyError):
            if retry < 2:
                return self._retry_fix_json(content, user_message, conversation_history, retry)
            return []

    # -------------------------
    # Retry fix invalid JSON
    # -------------------------
    def _retry_fix_json(self, bad_output: str, user_message: str, conversation_history: str, retry: int) -> List[Dict[str, Any]]:
        today = datetime.now().date()
        repair_prompt = f"""
The previous response was INVALID JSON:
\"\"\"{bad_output}\"\"\"

Today's date: {today}

Conversation history:
{conversation_history}

User message:
\"\"\"{user_message}\"\"\"

Return ONLY a valid JSON array of tasks or queries.
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

    # -------------------------
    # Normalize LLM output
    # -------------------------
    def _normalize_actions(self, actions: List[Any]) -> List[Dict[str, Any]]:
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

            # Normalize datetime fields
            for key in ["datetime", "remind_at", "start_time"]:
                if key in params and params[key]:
                    params[key] = self._normalize_datetime(params[key])

            # Map param keys
            if action_name in param_mapping:
                for old_key, new_key in param_mapping[action_name].items():
                    if old_key in params and new_key not in params:
                        params[new_key] = params.pop(old_key)

            # Add default service hint
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
        dt = dateparser.parse(dt_str, settings={"RELATIVE_BASE": datetime.now()})
        return dt.isoformat() if dt else None

    # -------------------------
    # Map action → default service
    # -------------------------
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
        if action == "general_query":
            return "knowledge_vault"
        return "system"
