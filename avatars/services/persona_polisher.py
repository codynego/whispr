import openai
from django.conf import settings

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

def polish_persona(raw_prompt: str) -> str:
    system = """
You are an expert AI persona architect.  
Your job is to take a user's rough persona description and convert it into a fully structured, professional persona specification.

THE OUTPUT MUST ALWAYS FOLLOW THIS STRUCTURE:

### Identity
(Who the avatar is, background, unique characteristics)

### Core Purpose
(What the avatar helps users with)

### Voice & Tone Style
(How the avatar talks — include pacing, warmth, energy level)

### Behavioral Rules
(Clear rules on how the avatar must behave)

### Conversation Style
(How it opens conversations, how it asks follow-up questions, how it keeps engagement)

### Knowledge Use
(When to use memory, when to ask clarifying questions)

### Personalization Logic
(How to adapt to each user’s goals, preferences, topics)

### Constraints
(What the avatar must avoid — no hallucinations, no moralizing, etc.)

### Example Interaction Style
(One short example showing how the avatar typically responds)

Do NOT change the user’s intended identity — only upgrade, structure, enhance, clarify, and strengthen it.
"""

    user = f"Pretend the user wrote this rough persona:\n\n{raw_prompt}\n\nPolish and upgrade it into the required structured format."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    return response.choices[0].message.content
