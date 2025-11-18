# whisone/tasks/openai_client.py

import json
from typing import Any, Dict, List

from openai import OpenAI
from django.conf import settings

# Initialize the client once (best practice)
client = OpenAI(api_key=settings.OPENAI_API_KEY)


DAILY_SUMMARY_PROMPT = """
You are WhisOne, a personal AI assistant. Your job is to generate a clear,
helpful daily summary based strictly on the data provided. Do NOT invent
events, emails, tasks, or reminders.

Here is the user’s data:

Emails:
{emails}

Calendar Events:
{calendar}

Todos:
{todos}

Reminders:
{reminders}

Notes:
{notes}

Write a friendly, structured daily summary with the following sections:

---

Morning Briefing
One or two sentences giving a friendly greeting and overview of the day.

Important Emails
- Summaries of only important or recent emails
- If nothing important, say: "No important emails."

Today’s Schedule
- Events in chronological order
- Show time and title
- If calendar is empty, say so.

Tasks & Todos
- Overdue tasks first
- Due today next
- Upcoming tasks if relevant

Reminders
- Upcoming reminders with times

Notes (Optional)
- Recently updated notes (if provided)

Smart Suggestion
Provide ONE personalized suggestion based on patterns:
- e.g. "You have free time at 2 PM — want me to set a focus block?"

Be concise, friendly, and avoid long paragraphs.
"""


def generate_daily_summary(data: Dict[str, Any]) -> str:
    """
    Generate a clean daily summary using OpenAI (v1+ client).
    """
    # Safely extract lists with defaults
    emails = data.get("emails") or []
    calendar = data.get("calendar") or []
    todos = data.get("todos") or []
    reminders = data.get("reminders") or []
    notes = data.get("notes") or []

    prompt = DAILY_SUMMARY_PROMPT.format(
        emails=_format_section(emails),
        calendar=_format_section(calendar),
        todos=_format_section(todos),
        reminders=_format_section(reminders),
        notes=_format_section(notes),
    )

    # New v1+ syntax
    response = client.chat.completions.create(
        model="gpt-4o-mini",           # Recommended: use gpt-4o-mini or gpt-4o (gpt-5.1 doesn't exist yet)
        messages=[
            {"role": "system", "content": "You are a concise, friendly daily planning assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=1500,
    )

    return response.choices[0].message.content.strip()


def _format_section(items: List[Any]) -> str:
    """
    Safely format a list of dicts/objects as pretty JSON.
    Falls back to repr() if not JSON-serializable.
    """
    if not items:
        return "None"

    try:
        return json.dumps(items, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        # Fallback for objects that aren't directly serializable
        return "\n".join(str(item) for item in items)