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
    Includes:
    - Context-aware planning using previous messages.
    - Keyword extraction for fetch/search operations.
    """

    FETCH_ACTIONS = {
        "fetch_emails",
        "fetch_events",
        "fetch_todos",
        "fetch_notes",
        "fetch_reminders",
    }

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini", history_limit: int = 3):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.model = model
        self.history_limit = history_limit

    # ---------------------------------------------------------------------
    # MAIN ENTRY
    # ---------------------------------------------------------------------
    def plan_tasks(self, user: User, user_message: str) -> List[Dict[str, Any]]:
        """Create structured tasks from natural language."""
        
        # Load recent conversation history
        history_msgs = AssistantMessage.objects.filter(user=user).order_by("-created_at")[:self.history_limit]
        history_msgs = reversed(history_msgs)

        conversation_history = "\n".join(
            ("User: " if msg.role == "user" else "Assistant: ") + msg.content
            for msg in history_msgs
        )

        # Get raw actions from LLM
        raw_actions = self._call_llm(user_message, conversation_history)

        # Normalize + keyword extraction
        return self._normalize_actions(raw_actions, original_message=user_message)

    # ---------------------------------------------------------------------
    # LLM CALL
    # ---------------------------------------------------------------------
    def _call_llm(self, user_message: str, conversation_history: str, retry: int = 0) -> List[Dict[str, Any]]:
        today = datetime.now().date()

        prompt = (
            "You are the Whisone Task Planner. Convert user text into structured JSON actions.\n\n"
            f"Conversation history:\n{conversation_history}\n\n"
            f"Today's date: {today}\n\n"
            f"User message:\n\"\"\"{user_message}\"\"\"\n\n"

            "Output Rules:\n"
            "- Return ONLY a JSON array.\n"
            "- Each item must include: action, params, intent, confidence.\n"
            "- Dates must be ISO8601.\n"
            "- If the user is searching emails/events/notes/todos/reminders, extract FILTER KEYWORDS as a list.\n"
            "- Do NOT write explanations.\n\n"

            "Supported actions:\n"
            "[\"create_note\",\"update_note\",\"delete_note\","
            "\"create_reminder\",\"update_reminder\",\"delete_reminder\","
            "\"add_todo\",\"update_todo\",\"delete_todo\","
            "\"create_event\",\"update_event\",\"delete_event\",\"fetch_events\","
            "\"fetch_emails\",\"mark_email_read\",\"send_email\","
            "\"fetch_todos\",\"fetch_notes\",\"fetch_reminders\"]"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Convert natural language into machine-readable JSON tasks."},
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content

        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            if retry < 2:
                return self._retry_fix_json(content, user_message, conversation_history, retry)
            return []

    # ---------------------------------------------------------------------
    # FIX INVALID JSON
    # ---------------------------------------------------------------------
    def _retry_fix_json(self, bad_output: str, user_message: str, history: str, retry: int):
        today = datetime.now().date()

        prompt = f"""
The previous response was invalid JSON:

\"\"\"{bad_output}\"\"\"

Fix it. Return ONLY valid JSON.

Conversation:
{history}

User message:
\"\"\"{user_message}\"\"\"

Today's date: {today}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt}
            ]
        )

        try:
            return json.loads(response.choices[0].message.content)
        except:
            return []

    # ---------------------------------------------------------------------
    # NORMALIZATION + KEYWORD EXTRACTION
    # ---------------------------------------------------------------------
    def _normalize_actions(self, actions: List[Dict[str, Any]], original_message: str) -> List[Dict[str, Any]]:
        cleaned = []

        for task in actions:
            action = task.get("action")
            params = task.get("params", {})
            intent = task.get("intent", action)
            confidence = float(task.get("confidence", 0.90))

            # Normalize datetime
            if "datetime" in params:
                params["datetime"] = self._normalize_datetime(params["datetime"])

            # Infer service (if missing)
            if "service" not in params:
                params["service"] = self._infer_service(action)

            # -----------------------------
            # 🔥 NEW: Keyword extraction
            # -----------------------------
            if action in self.FETCH_ACTIONS:
                params["filters"] = self._extract_keywords(original_message)

            cleaned.append({
                "action": action,
                "params": params,
                "intent": intent,
                "confidence": confidence
            })

        return cleaned

    # ---------------------------------------------------------------------
    # NATURAL DATE PARSE
    # ---------------------------------------------------------------------
    def _normalize_datetime(self, dt_str: str) -> Optional[str]:
        if not dt_str:
            return None
        result = dateparser.parse(dt_str, settings={"RELATIVE_BASE": datetime.now()})
        return result.isoformat() if result else None

    # ---------------------------------------------------------------------
    # SERVICE INFERENCE
    # ---------------------------------------------------------------------
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

    # ---------------------------------------------------------------------
    # 🔥 NEW: KEYWORD EXTRACTION LOGIC
    # ---------------------------------------------------------------------
    def _extract_keywords(self, message: str) -> List[str]:
        """
        Extract meaningful search keywords.
        E.g. "show me amazon payment emails" → ["amazon", "payment"]
        """
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Extract concise search keywords from the message. Return JSON list only."},
                {"role": "user", "content": f"Message: {message}\nReturn only a JSON list of keywords."}
            ]
        )

        try:
            return json.loads(response.choices[0].message.content)
        except:
            return []
