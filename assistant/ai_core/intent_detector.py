# import google.generativeai as genai
# from typing import Dict, Any, Optional
# import os
# import re
# import json


# class IntentDetector:
#     """
#     Detects user intent and entities using either explicit @commands
#     or fallback to Gemini for free-form messages.
#     """

#     def __init__(self, api_key: Optional[str] = None):
#         self.api_key = api_key or os.getenv("GEMINI_API_KEY")
#         genai.configure(api_key=self.api_key)
#         self.model = genai.GenerativeModel("gemini-2.5-flash")

#         # 🔹 Map @commands → intents
#         self.command_map = {
#             "@find": "find_email",
#             "@send": "send_message",
#             "@summarize": "summarize_email",
#             "@task": "find_task",
#             "@meeting": "find_meeting",
#             "@doc": "find_document",
#         }

#     # --------------------------------------------------------
#     # 🧠 DETECT INTENT
#     # --------------------------------------------------------
#     def detect_intent(
#         self, message: str, previous_context: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """
#         Determines the user intent and entities.
#         First tries to match an explicit @command, otherwise uses Gemini.
#         """
#         message_lower = message.lower().strip()

#         # 1️⃣ Check for explicit @command
#         cmd_match = re.search(r"(@\w+)", message_lower)
#         if cmd_match:
#             command = cmd_match.group(1)
#             print("Detected explicit command:", command)

#             if command in self.command_map:
#                 intent = self.command_map[command]
#                 entities = self._extract_entities(message)
#                 print(f"Mapped {command} → {intent}")
#                 return {
#                     "intent": intent,
#                     "confidence": 1.0,
#                     "entities": entities,
#                     "source": "command",
#                 }

#         # 2️⃣ Otherwise fallback to Gemini
#         print("No explicit command found — using Gemini for intent detection.")
#         return self._detect_with_gemini(message, previous_context)

#     # --------------------------------------------------------
#     # 🤖 GEMINI INTENT DETECTION
#     # --------------------------------------------------------
#     def _detect_with_gemini(
#         self, message: str, previous_context: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """
#         Uses Gemini to extract structured intent and entities from text.
#         """
#         system_prompt = """
#         You are an AI assistant that analyzes a user's message to determine:
#         1. The intent (what the user wants to do)
#         2. The entities (specific details like sender, timeframe, subject, etc.)

#         Return ONLY a valid JSON object like this:
#         {
#             "intent": "<one of: read_message, find_email, find_transaction, find_task, find_meeting, send_message, find_document, summarize_email>",
#             "confidence": <float between 0 and 1>,
#             "entities": {
#                 "<entity_name>": "<entity_value>"
#             }
#         }
#         """

#         try:
#             user_prompt = f"User message: {message}\nPrevious context: {previous_context or {}}"
#             response = self.model.generate_content(f"{system_prompt}\n\n{user_prompt}")

#             raw_text = response.text.strip()
#             print("Gemini Raw Response:", raw_text)

#             # Remove markdown code fences
#             clean_text = re.sub(r"^```(?:json)?|```$", "", raw_text, flags=re.MULTILINE).strip()

#             try:
#                 parsed = json.loads(clean_text)
#             except json.JSONDecodeError:
#                 print("⚠️ Could not decode JSON, fallback to defaults.")
#                 parsed = {}

#             parsed.setdefault("intent", "unknown")
#             parsed.setdefault("confidence", 0.5)
#             parsed.setdefault("entities", {})

#             print("Gemini Intent Detection Result:", parsed)
#             return parsed

#         except Exception as e:
#             print("Gemini Intent Detection Error:", e)
#             return {
#                 "intent": "unknown",
#                 "confidence": 0.0,
#                 "entities": {},
#             }

#     # --------------------------------------------------------
#     # 🔍 BASIC ENTITY EXTRACTION (regex fallback)
#     # --------------------------------------------------------
#     def _extract_entities(self, message: str) -> Dict[str, str]:
#         """
#         Basic regex-based entity extraction.
#         (Lightweight backup if Gemini isn't used)
#         """
#         entities = {}

#         # Detect sender
#         match_sender = re.search(r"from\s+([A-Za-z0-9&.\s]+)", message)
#         if match_sender:
#             entities["sender"] = match_sender.group(1).strip()

#         # Detect timeframe
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




from typing import Dict, Any, Optional
import os
import re
import json
import spacy


class IntentDetector:
    """
    Detects user intent and entities using explicit @commands
    or rule-based keyword matching for intent and NER for entities.
    """

    def __init__(self, api_key: Optional[str] = None):
        # Load spaCy model for NER
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise ValueError("spaCy model 'en_core_web_sm' not found. Please install it with: python -m spacy download en_core_web_sm")

        # 🔹 Map @commands → intents
        self.command_map = {
            "@find": "find_email",
            "@send": "send_message",
            "@summarize": "summarize_email",
            "@task": "find_task",
            "@meeting": "find_meeting",
            "@doc": "find_document",
        }

        # 🔹 Keyword-based intent mapping
        self.intent_keywords = {
            "find_email": ["email", "mail", "inbox"],
            "send_message": ["send", "reply", "message"],
            "summarize_email": ["summarize", "summary"],
            "find_task": ["task", "todo"],
            "find_meeting": ["meeting", "calendar"],
            "find_document": ["document", "file", "doc"],
            "find_transaction": ["transaction", "bank", "payment"],
            "read_message": ["read", "open"],
        }

    # --------------------------------------------------------
    # 🧠 DETECT INTENT
    # --------------------------------------------------------
    def detect_intent(
        self, message: str, previous_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Determines the user intent and entities.
        First tries to match an explicit @command, otherwise uses rule-based keyword matching for intent and NER for entities.
        """
        message_lower = message.lower().strip()

        # 1️⃣ Check for explicit @command
        cmd_match = re.search(r"(@\w+)", message_lower)
        if cmd_match:
            command = cmd_match.group(1)
            print("Detected explicit command:", command)

            if command in self.command_map:
                intent = self.command_map[command]
                entities = self._extract_entities_with_ner(message)
                print(f"Mapped {command} → {intent}")
                return {
                    "intent": intent,
                    "confidence": 1.0,
                    "entities": entities,
                    "source": "command",
                }

        # 2️⃣ Otherwise fallback to rule-based intent detection + NER
        print("No explicit command found — using rule-based intent and NER for entities.")
        return self._detect_with_rules_and_ner(message, previous_context)

    # --------------------------------------------------------
    # 📝 RULE-BASED INTENT DETECTION + NER
    # --------------------------------------------------------
    def _detect_with_rules_and_ner(
        self, message: str, previous_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Uses keyword matching to detect intent from text, and spaCy NER for entities.
        """
        message_lower = message.lower()
        intent = "unknown"
        confidence = 0.0
        max_matches = 0

        for possible_intent, keywords in self.intent_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in message_lower)
            if matches > max_matches:
                max_matches = matches
                intent = possible_intent
                confidence = min(1.0, matches / len(keywords))

        if max_matches == 0:
            confidence = 0.0

        # Extract entities using NER
        entities = self._extract_entities_with_ner(message)

        result = {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "source": "rules_ner",
        }

        print("Rule-based + NER Detection Result:", result)
        return result

    # --------------------------------------------------------
    # 🔍 ENTITY EXTRACTION WITH NER (spaCy + regex fallback)
    # --------------------------------------------------------
    def _extract_entities_with_ner(self, message: str) -> Dict[str, str]:
        """
        Extracts entities using spaCy NER for named entities and regex for others.
        """
        entities = {}

        # spaCy NER
        doc = self.nlp(message)
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG"]:
                entities["sender"] = ent.text  # Sender could be person or organization
            elif ent.label_ == "DATE":
                entities["timeframe"] = ent.text
            # Add more mappings as needed, e.g., MONEY for transactions

        # Regex fallbacks for non-NER entities
        message_lower = message.lower()

        # Detect sender (if not already from NER)
        if "sender" not in entities:
            match_sender = re.search(r"from\s+([A-Za-z0-9&.\s]+)", message)
            if match_sender:
                entities["sender"] = match_sender.group(1).strip()

        # Detect timeframe (enhance if not from NER)
        if "timeframe" not in entities:
            if "yesterday" in message_lower:
                entities["timeframe"] = "yesterday"
            elif "last week" in message_lower:
                entities["timeframe"] = "last_week"
            elif "today" in message_lower:
                entities["timeframe"] = "today"

        # Detect transaction type
        if "credit" in message_lower:
            entities["type"] = "credit"
        elif "debit" in message_lower:
            entities["type"] = "debit"

        # Detect subject
        match_subject = re.search(r"subject[:\s]+(.+?)(?:\n|$)", message, re.IGNORECASE | re.DOTALL)
        if match_subject:
            entities["subject"] = match_subject.group(1).strip()

        return entities