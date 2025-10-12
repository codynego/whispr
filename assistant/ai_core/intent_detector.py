# # whispr/ai_core/intent_detector.py

# from typing import Dict, Any, Optional
# import re

# class IntentDetector:
#     """
#     Detects user intent from text input and optionally merges it with previous context.
#     In production, this could be replaced by a small intent classification model.
#     """

#     def __init__(self):
#         # Define supported intents and their keyword triggers
#         self.intent_keywords = {
#             "find_email": ["email", "mail", "message", "inbox", "sent", "important"],
#             "find_transaction": ["credit", "debit", "alert", "transaction", "payment"],
#             "find_task": ["task", "todo", "follow-up", "reminder"],
#             "find_meeting": ["meeting", "call", "appointment", "schedule"],
#             "find_document": ["file", "document", "attachment", "pdf"],
#             "send_message": ["reply", "respond", "send", "forward"],
#             "find_project_updates": ["project", "update", "status", "progress"]
#         }

#     def detect_intent(self, message: str, previous_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
#         """
#         Returns a structured intent object like:
#         {
#             "intent": "find_email",
#             "confidence": 0.92,
#             "entities": {"sender": "ALX"}
#         }
#         """
#         message_lower = message.lower()
#         detected_intent = None
#         confidence = 0.0

#         # Simple keyword-based intent detection
#         for intent, keywords in self.intent_keywords.items():
#             for keyword in keywords:
#                 if keyword in message_lower:
#                     detected_intent = intent
#                     confidence = 0.9
#                     break
#             if detected_intent:
#                 break

#         # Fallback: if context exists but no intent detected, reuse previous one
#         if not detected_intent and previous_context:
#             detected_intent = previous_context.get("intent")
#             confidence = 0.6

#         # Basic entity extraction (for demo)
#         entities = self._extract_entities(message)

#         return {
#             "intent": detected_intent or "unknown",
#             "confidence": confidence,
#             "entities": entities
#         }

#     def _extract_entities(self, message: str) -> Dict[str, str]:
#         """
#         Very basic regex-based entity extraction.
#         Replace this later with a Gemini or spaCy-powered extractor.
#         """
#         entities = {}

#         # Detect possible sender names or organizations
#         match_sender = re.search(r"from\s+([A-Za-z0-9&.\s]+)", message)
#         if match_sender:
#             entities["sender"] = match_sender.group(1).strip()

#         # Detect temporal clues
#         if "yesterday" in message.lower():
#             entities["timeframe"] = "yesterday"
#         elif "last week" in message.lower():
#             entities["timeframe"] = "last_week"
#         elif "today" in message.lower():
#             entities["timeframe"] = "today"

#         # Detect transaction type
#         if "credit" in message.lower():
#             entities["type"] = "credit"
#         elif "debit" in message.lower():
#             entities["type"] = "debit"

#         return entities





import google.generativeai as genai
from typing import Dict, Any, Optional
import os
import re
import json

class IntentDetector:
    """
    Uses Gemini to detect intent and extract entities from user messages.
    Returns a structured JSON payload with both intent and entities.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def detect_intent(self, message: str, previous_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Uses Gemini to extract structured intent and entities from text.
        Example return:
        {
            "intent": "find_email",
            "confidence": 0.94,
            "entities": {
                "sender": "ALX",
                "timeframe": "this week"
            }
        }
        """
        system_prompt = """
        You are an AI assistant that analyzes a user's message to determine:
        1. The intent (what the user wants to do)
        2. The entities (specific details like sender, timeframe, subject, etc.)

        Return your response **only** as a valid JSON object with this format:
        {
            "intent": "<string>",
            "confidence": <float between 0 and 1>,
            "entities": {
                "<entity_name>": "<entity_value>",
                ...
            }
        }

        Examples:
        - Input: "Did ALX send me a mail?"
          Output: {"intent": "find_email", "confidence": 0.93, "entities": {"sender": "ALX"}}

        - Input: "Reply to the message from John about the meeting"
          Output: {"intent": "send_message", "confidence": 0.95, "entities": {"recipient": "John", "topic": "meeting"}}

        - Input: "What’s on my schedule tomorrow?"
          Output: {"intent": "find_meeting", "confidence": 0.9, "entities": {"timeframe": "tomorrow"}}
        """

        try:
            user_prompt = f"User message: {message}\n\nPrevious context: {previous_context or {}}"
            response = self.model.generate_content(f"{system_prompt}\n\n{user_prompt}")
            print("Gemini Raw Response:", response.text.strip())

            # Try parsing Gemini’s structured JSON response
            raw_text = response.text.strip()
            print("Gemini Raw Response:", raw_text)

            # Clean Markdown code fences if present (```json ... ```)
            clean_text = re.sub(r"^```(?:json)?|```$", "", raw_text, flags=re.MULTILINE).strip()

            try:
                parsed = json.loads(clean_text)
            except json.JSONDecodeError:
                # If still not valid JSON, fall back to a safer partial parse
                print("Warning: Could not decode JSON, using fallback parsing.")
                parsed = {}

            # Sanitize output
            if "intent" not in parsed:
                parsed["intent"] = "unknown"
            if "confidence" not in parsed:
                parsed["confidence"] = 0.5
            if "entities" not in parsed:
                parsed["entities"] = {}

            print("Gemini Intent Detection Result:", parsed)
            return parsed

        except Exception as e:
            print("Gemini Intent Detection Error:", e)
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "entities": {}
            }
