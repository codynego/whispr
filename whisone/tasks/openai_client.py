
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

🌅 **Morning Briefing**
One or two sentences giving a friendly greeting and overview of the day.

📧 **Important Emails**
- Summaries of only important or recent emails
- If nothing important, say: "No important emails."

📅 **Today’s Schedule**
- Events in chronological order
- Show time and title
- If calendar is empty, say so.

📝 **Tasks & Todos**
- Overdue tasks first
- Due today next
- Upcoming tasks if relevant

⏰ **Reminders**
- Upcoming reminders with times

🗒️ **Notes (Optional)**
- Recently updated notes (if provided)

💡 **Smart Suggestion**
Provide ONE personalized suggestion based on patterns:
- e.g. "You have free time at 2 PM — want me to set a focus block?"

Be concise, friendly, and avoid long paragraphs.
"""


import openai
from django.conf import settings
import json

openai.api_key = settings.OPENAI_API_KEY


def generate_daily_summary(data):
    """
    Generate a clean daily summary using OpenAI.
    Input data must include:
    - emails
    - calendar
    - todos
    - reminders
    - notes
    """

    # Make sure none are missing
    emails = data.get("emails") or []
    calendar = data.get("calendar") or []
    todos = data.get("todos") or []
    reminders = data.get("reminders") or []
    notes = data.get("notes") or []

    prompt = DAILY_SUMMARY_PROMPT.format(
        emails=_format_json(emails),
        calendar=_format_json(calendar),
        todos=_format_json(todos),
        reminders=_format_json(reminders),
        notes=_format_json(notes)
    )

    response = openai.ChatCompletion.create(
        model="gpt-5.1",
        messages=[
            {"role": "system", "content": "You are a concise daily planning assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    summary = response["choices"][0]["message"]["content"]
    return summary




def _format_json(obj):
    try:
        return json.dumps(obj, indent=2)
    except:
        return str(obj)
