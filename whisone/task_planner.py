import json
import openai
import dateparser
from typing import List, Dict, Any, Optional


class TaskPlanner:
    """
    Converts natural language into structured tasks.
    Includes:
    - Multi-intent detection
    - Date & time normalization
    - Strict JSON enforcement
    - Retries for malformed output
    """

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=openai_api_key)
        self.model = model

    # -------------------------
    # Public entry
    # -------------------------
    def plan_tasks(self, user_message: str) -> List[Dict[str, Any]]:
        """
        Convert user natural language into structured action steps.
        Includes self-correction and date normalization.
        """
        raw_actions = self._call_llm(user_message)

        # Fix and validate actions
        cleaned_actions = self._normalize_actions(raw_actions)

        return cleaned_actions

    # -------------------------
    # INTERNAL: LLM call
    # -------------------------
    def _call_llm(self, user_message: str, retry: int = 0) -> List[Dict[str, Any]]:
        """
        Calls GPT model and ensures valid JSON is returned.
        Retries up to 2 times if JSON is malformed.
        """

        prompt = f"""
You are an AI Task Planner for an automation assistant called Whisone.

Your job:
1. Extract ALL tasks from the user's message.
2. Break multi-step instructions into separate actions.
3. Identify intent clearly.
4. Parse date/time expressions into ISO format (YYYY-MM-DDTHH:MM).
5. If date/time is vague, guess a reasonable time.
6. Include a confidence score (0–1).
7. ALWAYS return a valid JSON array.
8. NEVER include explanations, text, or code blocks — ONLY JSON.

Supported actions:
[
  "create_note", "update_note", "delete_note",
  "create_reminder", "update_reminder", "delete_reminder",
  "add_todo", "update_todo", "delete_todo",
  "fetch_emails", "mark_email_read",
  "create_event", "update_event", "delete_event",
  "send_email"
]

JSON Action Schema:
[
  {{
    "action": "create_reminder",
    "params": {{
        "title": "string",
        "datetime": "ISO8601 full timestamp or null",
        "recurrence": "optional",
        "service": "gmail|calendar|notes|todo|whatsapp|sms|system"
    }},
    "intent": "short natural language summary",
    "confidence": 0.90
  }}
]

User message:
\"\"\"{user_message}\"\"\"
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
            if isinstance(parsed, list):
                return parsed
            else:
                return []
        except json.JSONDecodeError:
            if retry < 2:
                return self._retry_fix_json(content, user_message, retry)
            return []

    # -------------------------
    # INTERNAL: Retry JSON fix
    # -------------------------
    def _retry_fix_json(self, bad_output: str, original_message: str, retry: int) -> List[Dict[str, Any]]:
        """
        Second chance to repair broken JSON.
        """

        repair_prompt = f"""
The previous response was INVALID JSON:
\"\"\"{bad_output}\"\"\"

Fix it. Return ONLY a valid JSON array of actions based on:

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
            return []  # Return empty actions if still bad

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
        Uses dateparser as a fallback.
        """
        result = dateparser.parse(dt_str)
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