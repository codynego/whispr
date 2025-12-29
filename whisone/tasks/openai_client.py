# whisone/tasks/openai_client.py

import json
from typing import Any, Dict, List

from openai import OpenAI
from django.conf import settings

# Initialize the client once
client = OpenAI(api_key=settings.OPENAI_API_KEY)


OVERALL_SUMMARY_PROMPT = """
You are WhisOne, a personal AI assistant. Your job is to generate a friendly,
human-style daily summary based strictly on the data provided. Do NOT invent
events, todos, reminders, or notes.

Focus on creating a single flowing paragraph that reads like a personal
reflection or past highlight of the day. Include:

- Past highlights from recent memories
- Overview of todos (overdue, due today) in a natural way
- Upcoming reminders
- Notes or insights that stand out

Do NOT create lists or tables. Write in a human-friendly, concise style.
Be encouraging and friendly.

Here is the user’s data:

Todos:
{todos}

Reminders:
{reminders}

Notes:
{notes}
"""

def generate_overall_daily_summary(user, data: Dict[str, Any]) -> str:
    """
    Generate an overall daily summary in a natural, human-readable style.
    """
    print("Generating overall daily summary with data:", data)
    todos = data.get("todos") or {"overdue": [], "today": []}
    reminders = data.get("reminders") or []
    notes = data.get("notes") or []

    prompt = OVERALL_SUMMARY_PROMPT.format(
        todos=_format_section(todos),
        reminders=_format_section(reminders),
        notes=_format_section(notes),
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You write concise, friendly daily highlights."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=1000,
    )
    print("OpenAI response:", response)
    return response.choices[0].message.content.strip()


def _format_section(section: Any) -> str:
    """
    Safely format section data for the prompt.
    Converts dicts/lists to JSON string, fallback to str().
    """
    if not section:
        return "None"

    try:
        return json.dumps(section, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(section)
