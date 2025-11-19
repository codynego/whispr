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
    Converts natural language into structured tasks or general queries.
    Supports context-aware planning using recent user messages.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", history_limit: int = 2):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.history_limit = history_limit

    def plan_tasks(self, user: User, user_message: str) -> List[Dict[str, Any]]:
        """
        Convert user natural language into structured action steps or general queries.
        """
        # 1️⃣ Build conversation history
        history_msgs = AssistantMessage.objects.filter(user=user).order_by("-created_at")[:self.history_limit]
        history_msgs = reversed(history_msgs)
        conversation_history = ""
        for msg in history_msgs:
            role = "User" if msg.role == "user" else "Assistant"
            conversation_history += f"{role}: {msg.content}\n"

        # 2️⃣ Call LLM
        raw_actions = self._call_llm(user_message, conversation_history)

        # 3️⃣ Normalize actions
        cleaned_actions = self._normalize_actions(raw_actions)
        return cleaned_actions

    # -------------------------
    # LLM call
    # -------------------------
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
            "2. Identify if the user is asking a general query (information retrieval) instead of creating a task, please dont mix it with fetch_emails.\n"
            "3. For general queries, extract structured vault query fields: entity_type, topic/keyword, time_range, filters.\n"
            "4. Break multi-step instructions into separate actions.\n"
            "5. Parse date/time expressions into ISO8601 format (YYYY-MM-DDTHH:MM).\n"
            "6. Include a confidence score (0–1).\n"
            "7. ALWAYS return a valid JSON array of task objects.\n"
            "8. NEVER include explanations, text, or code blocks — ONLY JSON.\n\n"
            "9. dont misclasify general queries like 'Who did I meet this week?' as fetch_emails or other task types. such queries should be classified as 'general_query' with appropriate parameters for knowledge vault search.\n\n"
            "10. and query like 'whats in my email', 'check my email', 'whats in my inbox' should be classified as 'fetch_emails' task.\n\n"
            "11. query like 'show my notes', 'what are my notes' should be classified as 'fetch_notes' task.\n\n"
            "12. query like 'what are my todos', 'show my todos' should be classified as 'fetch_todos' task.\n\n"
            "13. query like 'what are my reminders', 'show my reminders' should be classified as 'fetch_reminders' task.\n\n"
            "14. if the user query is not related to email fetching, note fetching, todo fetching and reminder fetching, and is more of a general information query, classify it as 'general_query'.\n\n"
            "Action Mapping:\n"
            "- Notes: create_note, update_note, delete_note, fetch_notes\n"
            "- Reminders: create_reminder, update_reminder, delete_reminder, fetch_reminders\n"
            "- Todos: create_todo, update_todo, delete_todo, fetch_todos\n"
            "- Calendar: create_event, update_event, delete_event, fetch_events\n"
            "- Emails: fetch_emails, mark_email_read, send_email\n"
            "- General Queries: general_query (for general info not related to email fetching, note fetching, todo fecthing and reminder fetching)\n\n"
            "Return ONLY JSON array. Examples:\n"
            "[\n"
            "  {\"action\": \"create_note\", \"params\": {\"content\": \"Buy milk\"}, \"intent\": \"Create a note to buy milk\", \"confidence\": 0.9},\n"
            "  {\"action\": \"create_reminder\", \"params\": {\"text\": \"Attend meeting\", \"remind_at\": \"2025-11-17T14:00\"}, \"intent\": \"Set a reminder to attend meeting\", \"confidence\": 0.95},\n"
            "  {\"action\": \"general_query\", \"params\": {\"entity_type\": \"events\", \"topic\": \"meeting\", \"time_range\": {\"start\": \"2025-11-17T00:00\", \"end\": \"2025-11-23T23:59\"}}, \"intent\": \"Who did I meet this week?\", \"confidence\": 0.95}\n"
            "]"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You convert natural language to structured JSON tasks or general queries."},
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

    # -------------------------
    # Retry fix for invalid JSON
    # -------------------------
    def _retry_fix_json(self, bad_output: str, original_message: str, conversation_history: str, retry: int) -> List[Dict[str, Any]]:
        today = datetime.now().date()
        repair_prompt = f"""
The previous response was INVALID JSON:
\"\"\"{bad_output}\"\"\"

Today's date is {today}.

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
    # Normalize actions
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

            # -------- Date normalization --------
            for key in ["datetime", "remind_at", "start_time"]:
                if key in params and params[key]:
                    params[key] = self._normalize_datetime(params[key])

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
        result = dateparser.parse(dt_str, settings={'RELATIVE_BASE': datetime.now()})
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
            return "whatsapp"
        if "todo" in action:
            return "todo"
        if action == "general_query":
            return "knowledge_vault"
        return "system"
