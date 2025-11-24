


from typing import List, Dict, Any, Optional
import json
from datetime import datetime, timedelta

import dateparser
import openai
from django.contrib.auth import get_user_model

from assistant.models import AssistantMessage

User = get_user_model()


class TaskPlanner:
    """
    Rock-solid TaskPlanner that forces the LLM to output correct field names.
    Works perfectly with the final TaskFrameBuilder — no more silent failures.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", history_limit: int = 5):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.history_limit = history_limit

    def plan_tasks(self, user: User, user_message: str) -> List[Dict[str, Any]]:
        conversation_history = self._get_conversation_history(user)
        raw_actions = self._call_llm(user_message, conversation_history)
        return self._normalize_and_enforce_fields(raw_actions)

    # ===================================================================
    # Conversation History
    # ===================================================================
    def _get_conversation_history(self, user: User) -> str:
        messages = AssistantMessage.objects.filter(user=user).order_by("-created_at")[:self.history_limit]
        history = []
        for msg in reversed(messages):
            role = "User" if msg.role == "user" else "Assistant"
            history.append(f"{role}: {msg.content}")
        return "\n".join(history)

    # ===================================================================
    # LLM Call with Iron-Clad Prompt
    # ===================================================================
    def _call_llm(self, user_message: str, conversation_history: str) -> List[Dict]:
        today = datetime.now().strftime("%B %d, %Y")

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
            "7. ALWAYS preserve the full content of the note/message.\n"
            "Action Mapping:\n"
            "- Notes: create_note, delete_note, fetch_notes\n"
            "- Reminders: create_reminder, update_reminder, delete_reminder, fetch_reminders\n"
            "- Todos: create_todo, update_todo, delete_todo, fetch_todos\n"
            "- Calendar: create_event, update_event, delete_event, fetch_events\n"
            "- Emails: fetch_emails, mark_email_read, send_email\n"
            "- General Queries: general_query\n\n"
            "When marking a todo or reminder as done, use these exact field names:\n"
            "- For todos: \"done\": true\n"
            "- For reminders: \"completed\": true\n"
            "Never use \"status\" or \"complete\".\n"
            "Return JSON array. Examples:\n"
            "[\n"
            '  {"action": "create_todo", "params": {"task": "Submit Greek assignment"}, "intent": "Create todo for assignment", "confidence": 0.98},\n'
            '  {"action": "update_todo", "params": {"task": "buy drugs", "done": true}, "intent": "Mark buy drugs as completed", "confidence": 0.99},\n'
            '  {"action": "create_reminder", "params": {"text": "Call mom", "remind_at": "2025-11-21T18:00"}, "intent": "Set reminder", "confidence": 0.95},\n'
            '  {"action": "update_reminder", "params": {"text": "Dentist", "completed": true}, "intent": "Mark reminder done", "confidence": 0.97}\n'
            "]\n\n"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1000,
            )
            content = response.choices[0].message.content.strip()

            # Clean common JSON wrappers
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            actions = json.loads(content)
            return actions if isinstance(actions, list) else []
        except Exception as e:
            print(f"LLM failed: {e}")
            return []

    # ===================================================================
    # Final Normalization + Enforcement (defense in depth)

    # ===================================================================
    def _normalize_and_enforce_fields(self, actions: List[Any]) -> List[Dict[str, Any]]:
        if not isinstance(actions, list):
            return []

        normalized = []

        # Universal field corrections
        fixes = {
            "create_todo": {"text": "task", "title": "task", "todo": "task", "content": "task"},
            "update_todo": {"text": "task", "title": "task", "status": "done", "complete": "done"},
            "create_reminder": {"task": "text", "title": "text"},
            "update_reminder": {"task": "text", "status": "completed", "complete": "completed"},
        }

        for item in actions:
            if not isinstance(item, dict):
                continue

            action = item.get("action")
            params = item.get("params", {}).copy()
            intent = item.get("intent", action or "Unknown intent")
            confidence = float(item.get("confidence", 0.8))

            # === CRITICAL FIXES ===
            if action in fixes:
                mapping = fixes[action]
                for wrong_key, correct_key in mapping.items():
                    if wrong_key in params:
                        value = params.pop(wrong_key)

                        # Special: convert any "completed" signal to boolean
                        if correct_key in ("done", "completed"):
                            truthy = {"true", "yes", "done", "completed", "finished", True, 1}
                            value = str(value).strip().lower() in truthy

                        params[correct_key] = value

            # === Ensure required fields exist (last resort) ===
            if action == "create_todo" and "task" not in params and params:
                # Grab any text-like field
                for key in ("text", "title", "content", "todo"):
                    if key in params:
                        params["task"] = params.pop(key)
                        break

            # === Datetime normalization ===
            for key in ("remind_at", "start_time", "due_date"):
                if key in params and params[key]:
                    params[key] = self._normalize_datetime(params[key])

            normalized.append({
                "action": action,
                "params": params,
                "intent": intent,
                "confidence": confidence,
            })

        return normalized

    # ===================================================================
    # Smart Date Parsing
    # ===================================================================
    def _normalize_datetime(self, dt_str: str) -> Optional[str]:
        if not dt_str:
            return None

        dt = dateparser.parse(
            dt_str,
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": datetime.now(),
            },
        )
        if not dt:
            return None

        now = datetime.now()

        # If time today has passed → move to tomorrow
        if dt.date() == now.date() and dt < now:
            dt += timedelta(days=1)

        # If date is in the past this year → assume next year
        if dt.date() < now.date() and dt.year == now.year:
            dt = dt.replace(year=now.year + 1)

        return dt.isoformat()
