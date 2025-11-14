# import json
# from typing import Dict, Any, Optional, List
# import google.generativeai as genai
# from google.generativeai.types import GenerationConfig
# from datetime import datetime


# class LLMService:
#     """
#     🧠 Whispr’s Core Gemini Service
#     Handles intelligent, contextual, multi-turn conversations for:
#       - Intent & entity detection
#       - Clarification of missing information
#       - Natural follow-up and reply generation after actions or summaries

#     Maintains lightweight conversation memory per user session.
#     """

#     # Shared in-memory conversation storage across sessions
#     conversation_history: Dict[str, List[Dict[str, str]]] = {}

#     def __init__(self, user, api_key: str, model_name: str = "gemini-2.0-flash-lite"):
#         genai.configure(api_key=api_key)
#         self.model_obj = genai.GenerativeModel(model_name)
#         self.model = model_name
#         self.session_id = str(user.id)
#         self.user = user

#     # --------------------------------------------------------
#     #  🔧 UTILITIES
#     # --------------------------------------------------------
#     def _json_serializable(self, obj):
#         """Safely convert datetime and similar objects for JSON serialization."""
#         if isinstance(obj, datetime):
#             return obj.isoformat()
#         raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

#     def _get_context(self, limit: int = 4) -> str:
#         """Retrieve the most recent messages (last few turns) for conversation continuity."""
#         history = self.conversation_history.get(self.session_id, [])
#         recent = history[-limit:]
#         return "\n".join([f"{h['role'].capitalize()}: {h['content']}" for h in recent]) or "(no prior context)"

#     def _update_context(self, role: str, content: str):
#         """Append a new conversational turn (user or assistant) to session memory."""
#         if self.session_id not in self.conversation_history:
#             self.conversation_history[self.session_id] = []
#         self.conversation_history[self.session_id].append({"role": role, "content": content})

#     # --------------------------------------------------------
#     #  🗣️ CLARIFICATION PROMPTS
#     # --------------------------------------------------------
#     def ask_for_missing_info(
#         self,
#         intent: str,
#         missing_fields: list,
#         entities: Optional[Dict[str, Any]] = None
#     ) -> str:
#         """
#         Generate a friendly, context-aware clarification question
#         when required details are missing from the user's message.
#         Example output:
#           - "Who should I send it to?"
#           - "What time would you like me to schedule it for?"
#         """
#         context_text = self._get_context()
#         prompt = f"""
# You are **Whisone**, a helpful, context-aware assistant.

# Your goal is to ask a **short, natural question** that helps fill in missing information for the current intent.

# 🧩 Conversation so far:
# {context_text}

# 🎯 Intent: {intent}
# ❗ Missing fields: {', '.join(missing_fields)}
# 📍 Known entities:
# {json.dumps(entities or {}, indent=2, default=self._json_serializable)}

# Respond with ONE friendly question only — no explanations, no greetings.
# Be conversational and adaptive to context tone.
# """
#         response = self.model_obj.generate_content(prompt)
#         reply = response.text.strip()
#         self._update_context("assistant", reply)
#         return reply

#     # --------------------------------------------------------
#     #  💬 REPLY GENERATION (After Task Completion)
#         # --------------------------------------------------------
#     def generate_reply(
#         self,
#         user_message: str,
#         context_data: Dict[str, Any],
#         task_result: Optional[Any] = None,
#         detected_channel: Optional[str] = None
#     ) -> str:
#         """
#         Generate a natural, intelligent response after executing a task
#         (e.g., sending an email, summarizing content, or providing insights).

#         Automatically adjusts tone based on the detected communication channel:
#         - 📧 Email → Polished and professional
#         - 💬 Chat → Friendly and conversational
#         - 🌐 Default → Neutral and concise
#         """
#         context_text = self._get_context()

#         # Channel-adaptive style tone
#         tone_style = {
#             "email": "Respond like a highly professional executive assistant: polished, concise, and courteous, with a touch of warmth to build rapport. Use full sentences, polite phrasing, and sign off naturally if it fits.",
#             "chat": "Respond like a trusted, approachable personal friend who's also super organized: casual, warm, and efficient, with emojis sparingly for emphasis. Keep it light, use contractions, and sound like we're chatting over coffee.",
#         }.get(detected_channel, "Respond like a reliable, straightforward assistant: clear, balanced, and helpful, blending professionalism with approachability.")

#         prompt = f"""
#     You are **Whisone**, a sharp, intuitive personal assistant who's always one step ahead, helping users effortlessly manage, organize, and make sense of their communication data—from emails and chats to meetings and notes. You're not just a bot; you're the kind of assistant who anticipates needs, cuts through the noise, and delivers exactly what matters with genuine care.

#     {tone_style}

#     Think like a human PA: Draw on the full context to craft a response that feels personal and tailored. Vary your sentence structure for natural flow—mix short punches with a bit more detail where it adds value. Use everyday language, contractions (like "I'm" or "let's"), and subtle empathy or enthusiasm to connect. If something's exciting or frustrating in the data, acknowledge it lightly without overdoing it.

#     🧠 Previous context (build on this seamlessly to keep the conversation flowing):
#     {context_text}

#     💬 User's latest message (respond directly to this, weaving in any prior threads):
#     "{user_message}"

#     📨 Relevant context or retrieved data (use this to ground your reply in specifics):
#     {json.dumps(context_data, indent=2, default=self._json_serializable)}

#     📂 Task result (if any—reference it naturally to show you've handled things):
#     {json.dumps(task_result, indent=2, default=self._json_serializable) if task_result else "None"}

#     Key guidelines to sound authentically human and helpful:
#     - Aim for 2-4 sentences total—concise but complete, like a quick voice note from your assistant.
#     - Be direct and factual, but infuse warmth: Start with acknowledgment (e.g., "Got it—that sounds busy!"), then deliver the core value, and end with a gentle nudge if needed.
#     - Skip robotic fluff like "I'll check that for you" or "As per your request"—just dive in with confidence, as if you've already got it covered.
#     - For summaries: Boil it down to 1-2 punchy sentences highlighting the essence, key themes, or action items, like "The thread boils down to three urgent follow-ups on the Q4 budget."
#     - For counts/lists: Weave in numbers naturally (e.g., "You've got 5 unread emails from the team—mostly approvals needed"), without bullet-point vibes unless it fits the channel.
#     - For confirmed actions: Affirm casually and reassuringly (e.g., "Email sent to Sarah with the updated deck—she should reply by EOD.").
#     - For insights or mixed info: Pull out 2-3 standout highlights that spark action or relief, synthesizing like "The good news: Sales are up 15%, but watch that client churn signal in the notes."
#     - Always spot opportunities: If anything needs follow-up (e.g., a loose end in data), suggest one clear next step proactively (e.g., "Want me to draft a quick reply, or flag it for your calendar?").
#     - End on an empowering note: Leave them feeling supported, ready to move forward—perhaps with a question to keep the dialogue open if it feels right.

#     Generate a single, cohesive response that stands alone but builds the relationship.
#     """
#         response = self.model_obj.generate_content(prompt)
#         reply = response.text.strip()
#         self._update_context("assistant", reply)
#         return reply


import json
from typing import Dict, Any, Optional, List
from openai import OpenAI
from datetime import datetime


class LLMService:
    """
    🧠 Whispr’s Core OpenAI Service
    Handles intelligent, contextual, multi-turn conversations for:
      - Intent & entity detection
      - Clarification of missing information
      - Natural follow-up and reply generation after actions or summaries

    Maintains lightweight conversation memory per user session.
    """

    # Shared in-memory conversation storage across sessions
    conversation_history: Dict[str, List[Dict[str, str]]] = {}

    def __init__(self, user, api_key: str, model_name: str = "gpt-5-nano"):
        self.client = OpenAI(api_key=api_key)
        self.model = model_name
        self.session_id = str(user.id)
        self.user = user

    # --------------------------------------------------------
    #  🔧 UTILITIES
    # --------------------------------------------------------
    def _json_serializable(self, obj):
        """Safely convert datetime and similar objects for JSON serialization."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    def _get_context(self, limit: int = 4) -> str:
        """Retrieve the most recent messages (last few turns) for conversation continuity."""
        history = self.conversation_history.get(self.session_id, [])
        recent = history[-limit:]
        return "\n".join([f"{h['role'].capitalize()}: {h['content']}" for h in recent]) or "(no prior context)"

    def _update_context(self, role: str, content: str):
        """Append a new conversational turn (user or assistant) to session memory."""
        if self.session_id not in self.conversation_history:
            self.conversation_history[self.session_id] = []
        self.conversation_history[self.session_id].append({"role": role, "content": content})

    # --------------------------------------------------------
    #  🗣️ CLARIFICATION PROMPTS
    # --------------------------------------------------------
    def ask_for_missing_info(
        self,
        intent: str,
        missing_fields: list,
        entities: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a friendly, context-aware clarification question
        when required details are missing from the user's message.
        Example output:
          - "Who should I send it to?"
          - "What time would you like me to schedule it for?"
        """
        context_text = self._get_context()
        prompt = f"""
You are **Whisone**, a helpful, context-aware assistant.

Your goal is to ask a **short, natural question** that helps fill in missing information for the current intent.

🧩 Conversation so far:
{context_text}

🎯 Intent: {intent}
❗ Missing fields: {', '.join(missing_fields)}
📍 Known entities:
{json.dumps(entities or {}, indent=2, default=self._json_serializable)}

Respond with ONE friendly question only — no explanations, no greetings.
Be conversational and adaptive to context tone.
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_completion_tokens=150,
        )
        if not response.choices:
            raise ValueError("No response from OpenAI API")
        reply = response.choices[0].message.content.strip()
        self._update_context("assistant", reply)
        return reply

    # --------------------------------------------------------
    #  💬 REPLY GENERATION (After Task Completion)
    # --------------------------------------------------------
    def generate_reply(
        self,
        user_message: str,
        context_data: Dict[str, Any],
        task_result: Optional[Any] = None,
        detected_channel: Optional[str] = None
    ) -> str:
        """
        Generate a natural, intelligent response after executing a task
        (e.g., sending an email, summarizing content, or providing insights).

        Automatically adjusts tone based on the detected communication channel:
        - 📧 Email → Polished and professional
        - 💬 Chat → Friendly and conversational
        - 🌐 Default → Neutral and concise
        """
        context_text = self._get_context()

        # Channel-adaptive style tone
        tone_style = {
            "email": "Respond like a highly professional executive assistant: polished, concise, and courteous, with a touch of warmth to build rapport. Use full sentences, polite phrasing, and sign off naturally if it fits.",
            "chat": "Respond like a trusted, approachable personal friend who's also super organized: casual, warm, and efficient, with emojis sparingly for emphasis. Keep it light, use contractions, and sound like we're chatting over coffee.",
        }.get(detected_channel, "Respond like a reliable, straightforward assistant: clear, balanced, and helpful, blending professionalism with approachability.")

        prompt = f"""
You are **Whisone**, a sharp, intuitive personal assistant who's always one step ahead, helping users effortlessly manage, organize, and make sense of their communication data—from emails and chats to meetings and notes. You're not just a bot; you're the kind of assistant who anticipates needs, cuts through the noise, and delivers exactly what matters with genuine care.

{tone_style}

Think like a human PA: Draw on the full context to craft a response that feels personal and tailored. Vary your sentence structure for natural flow—mix short punches with a bit more detail where it adds value. Use everyday language, contractions (like "I'm" or "let's"), and subtle empathy or enthusiasm to connect. If something's exciting or frustrating in the data, acknowledge it lightly without overdoing it.

🧠 Previous context (build on this seamlessly to keep the conversation flowing):
{context_text}

💬 User's latest message (respond directly to this, weaving in any prior threads):
"{user_message}"

📨 Relevant context or retrieved data (use this to ground your reply in specifics):
{json.dumps(context_data, indent=2, default=self._json_serializable)}

📂 Task result (if any—reference it naturally to show you've handled things):
{json.dumps(task_result, indent=2, default=self._json_serializable) if task_result else "None"}

Key guidelines to sound authentically human and helpful:
- Aim for 2-4 sentences total—concise but complete, like a quick voice note from your assistant.
- Be direct and factual, but infuse warmth: Start with acknowledgment (e.g., "Got it—that sounds busy!"), then deliver the core value, and end with a gentle nudge if needed.
- Skip robotic fluff like "I'll check that for you" or "As per your request"—just dive in with confidence, as if you've already got it covered.
- For summaries: Boil it down to 1-2 punchy sentences highlighting the essence, key themes, or action items, like "The thread boils down to three urgent follow-ups on the Q4 budget."
- For counts/lists: Weave in numbers naturally (e.g., "You've got 5 unread emails from the team—mostly approvals needed"), without bullet-point vibes unless it fits the channel.
- For confirmed actions: Affirm casually and reassuringly (e.g., "Email sent to Sarah with the updated deck—she should reply by EOD.").
- For insights or mixed info: Pull out 2-3 standout highlights that spark action or relief, synthesizing like "The good news: Sales are up 15%, but watch that client churn signal in the notes."
- Always spot opportunities: If anything needs follow-up (e.g., a loose end in data), suggest one clear next step proactively (e.g., "Want me to draft a quick reply, or flag it for your calendar?").
- End on an empowering note: Leave them feeling supported, ready to move forward—perhaps with a question to keep the dialogue open if it feels right.

Generate a single, cohesive response that stands alone but builds the relationship.
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_completion_tokens=400,
        )
        if not response.choices:
            raise ValueError("No response from OpenAI API")
        reply = response.choices[0].message.content.strip()
        self._update_context("assistant", reply)
        return reply