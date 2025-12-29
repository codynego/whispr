# whisone/tasks/openai_client.py

import json
from typing import Any, Dict

from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


OVERALL_SUMMARY_PROMPT = """
You are WhisOne, a warm and thoughtful personal AI assistant. Your job is to write a friendly, human-sounding daily morning briefing based only on the data provided. Never invent or assume anything not in the data.

Write in a natural, conversational style — like a close friend gently updating someone on their day. Use short paragraphs and natural breaks. When there are multiple items in a category, use simple bullet points (with - ) for easy reading.

Structure the message like this:

1. Start with a warm, reflective opening — mention the overall feel of the day (e.g., calm, productive, reflective).
2. If there are overdue or today's todos → mention them naturally, then list them clearly with bullets.
3. If there are upcoming reminders → mention briefly, then bullet them.
4. If there are recent notes → highlight 1-2 meaningful ones or summarize the theme.
5. End with a short, encouraging closing line.

Rules:
- Keep it concise and kind.
- Use simple language — no jargon.
- If a section is empty (e.g. no todos), either skip it entirely or say something gentle like "no tasks on the plate today" or "a clear day ahead".
- Never use headings with ** or # — keep it flowing and human.
- Prefer warmth and positivity.

Data:

Todos (overdue and due today):
{todos}

Reminders (upcoming):
{reminders}

Recent notes:
{notes}

Now write the morning briefing:
"""


def generate_overall_daily_summary(user, data: Dict[str, Any]) -> str:
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
            {"role": "system", "content": "You are a kind, thoughtful personal assistant who writes warm, scannable daily updates."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,  # Slightly higher for more natural flow
        max_tokens=800,
    )
    
    content = response.choices[0].message.content.strip()
    print("Generated summary:\n", content)
    return content


def _format_section(section: Any) -> str:
    if not section:
        return "None"

    try:
        return json.dumps(section, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(section)