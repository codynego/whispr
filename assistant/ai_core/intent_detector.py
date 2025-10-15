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
import os
import re
import spacy
import json
import google.generativeai as genai
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
from dateutil import parser as date_parser
import dateparser



# ----------------- Embedding Helper ----------------- #
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def generate_embedding(text: str):
    """Generate normalized sentence embeddings."""
    if not text or not text.strip():
        return []
    embedding = embedding_model.encode([text], normalize_embeddings=True)
    return embedding[0].tolist()


# ----------------- Intent Detector ----------------- #
class IntentDetector:
    """
    Detects user intent and entities using explicit @commands,
    rule-based logic, NER, and selectively calls LLM
    for complex message types like send/reply/task/reminder.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

        # Load spaCy NER model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise ValueError("Please install spaCy model: python -m spacy download en_core_web_sm")

        # Command mapping
        self.command_map = {
            "@read": "read_email",
            "@find": "find_email",
            "@send": "send_email",
            "@reply": "reply_email",
            "@summarize": "summarize_email",
            "@task": "create_task",
            "@meeting": "find_meeting",
            "@doc": "find_document",
            "@remind": "set_reminder",
        }

        # Keyword intent hints
        self.intent_keywords = {
            "read_email": ["read", "open"],
            "find_email": ["email", "mail", "inbox"],
            "send_email": ["send", "compose", "email"],
            "reply_email": ["reply", "respond"],
            "summarize_email": ["summarize", "summary"],
            "create_task": ["task", "todo", "schedule"],
            "set_reminder": ["remind", "remember", "by", "at", "in"],
            "find_meeting": ["meeting", "calendar"],
            "find_document": ["document", "file", "doc"],
        }

    # ----------------- Detect Intent ----------------- #
    def detect_intent(self, message: str, previous_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Main entry point to detect intent and extract structured entities."""
        message_lower = message.lower().strip()

        # 1️⃣ Explicit command check
        cmd_match = re.search(r"(@\w+)", message_lower)
        if cmd_match:
            command = cmd_match.group(1)
            if command in self.command_map:
                intent = self.command_map[command]
                entities = self._extract_entities(message)
                print(f"🧭 Explicit command detected: {command} → {intent}")

                # Use LLM for structured extraction
                if intent in ["send_email", "reply_email"]:
                    entities.update(self._extract_send_reply_entities_with_llm(message))
                elif intent in ["create_task", "set_reminder"]:
                    entities.update(self._extract_task_entities_with_llm(message))
                    entities["input_text"] = message  # Preserve original text

                return {
                    "intent": intent,
                    "confidence": 1.0,
                    "entities": entities,
                    "source": "command",
                }

        # 2️⃣ Rule-based fallback
        result = self._detect_with_rules_and_ner(message)
        intent = result["intent"]
        print(f"🧭 Rule-based intent detected: {intent}")

        if intent in ["send_email", "reply_email"]:
            result["entities"].update(self._extract_send_reply_entities_with_llm(message))
        elif intent in ["create_task", "set_reminder"]:
            result["entities"].update(self._extract_task_entities_with_llm(message))
            result["entities"]["input_text"] = message  # Preserve original text

        return result

    # ----------------- Rules + NER ----------------- #
    def _detect_with_rules_and_ner(self, message: str) -> Dict[str, Any]:
        """Uses keyword matching and NER to guess intent."""
        message_lower = message.lower()
        intent = "unknown"
        confidence = 0.0
        best_match = 0

        for possible_intent, keywords in self.intent_keywords.items():
            matches = sum(1 for kw in keywords if kw in message_lower)
            if matches > best_match:
                best_match = matches
                intent = possible_intent
                confidence = min(1.0, matches / len(keywords))

        entities = self._extract_entities(message)
        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "source": "rules_ner",
        }

    # ----------------- Entity Extraction ----------------- #
    def _extract_entities(self, message: str) -> Dict[str, str]:
        """Extracts people, orgs, and time-related entities using spaCy + regex."""
        entities = {}
        doc = self.nlp(message)

        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG"] and "sender" not in entities:
                entities["sender"] = ent.text
            elif ent.label_ == "DATE" and "timeframe" not in entities:
                entities["timeframe"] = ent.text

        # Fallbacks
        message_lower = message.lower()
        if "today" in message_lower:
            entities["timeframe"] = "today"
        elif "yesterday" in message_lower:
            entities["timeframe"] = "yesterday"
        elif "tomorrow" in message_lower:
            entities["timeframe"] = "tomorrow"

        if "sender" not in entities:
            match_sender = re.search(r"from\s+([A-Za-z0-9&.\s]+)", message)
            if match_sender:
                entities["sender"] = match_sender.group(1).strip()

        if message.strip():
            entities["query_text"] = message.strip()

        return entities

    # ----------------- Email Entity Extraction via LLM ----------------- #
    def _extract_send_reply_entities_with_llm(self, message: str) -> Dict[str, Any]:
        """Extract recipient, subject, and email body using LLM."""
        llm_prompt = f"""
        You are Whispr, an AI email assistant.
        Extract structured email details from this message.

        Message: "{message}"

        Return only valid JSON:
        {{
            "receiver_name": "<name or empty>",
            "receiver_email": "<email if available>",
            "subject": "<generate subject if not provided>",
            "body": "<generate a clear and polite email body>"
        }}
        """
        try:
            response = self.model.generate_content(llm_prompt)
            raw = response.text.strip()
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)
            return parsed
        except Exception as e:
            print("⚠️ LLM email extraction failed:", e)
            return {"receiver_name": "", "receiver_email": "", "subject": "", "body": ""}

        # ----------------- Task Entity Extraction via LLM ----------------- #
    def _extract_task_entities_with_llm(self, message: str) -> Dict[str, Any]:
        llm_prompt = f"""
        You are Whispr, an AI assistant that manages tasks and reminders.
        Extract structured task information from the user's message.

        Message: "{message}"

        Return only valid JSON:
        {{
            "task_type": "<type of task or reminder list: email_send, reply, reminder, summarize, watch_incoming_emails>",
            "task_title": "<short summary of the task>",
            "due_time": "<specific time or datetime if mentioned, else empty>",
            "due_date": "<specific date if mentioned, else empty>",
            "action": "<type of action list: email_send, reply, reminder, summarize, watch_incoming_emails>",
            "context": "<extra context or who/what it's about>"
        }}
        """

        try:
            response = self.model.generate_content(llm_prompt)
            raw = response.text.strip()
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)

            # ---------------- Date/Time Normalization ----------------
            now = datetime.now()
            due_time_str = parsed.get("due_time", "").strip()
            due_date_str = parsed.get("due_date", "").strip()

            # Combine the date and time for parsing
            combined_text = f"{due_date_str} {due_time_str}".strip()
            parsed_dt = dateparser.parse(combined_text, settings={"RELATIVE_BASE": now})
            print("Parsed datetime:", parsed_dt)

            # Default logic
            if not parsed_dt:
                # Try parsing only time
                if due_time_str:
                    time_only = dateparser.parse(due_time_str, settings={"RELATIVE_BASE": now})
                    if time_only:
                        parsed_dt = datetime.combine(now.date(), time_only.time())
                        # If that time already passed, move to tomorrow
                        if parsed_dt < now:
                            parsed_dt += timedelta(days=1)
                # If nothing, default to 1 hour later
                if not parsed_dt:
                    parsed_dt = now + timedelta(hours=1)
            else:
                # If the parsed date/time is in the past, roll forward one day
                if parsed_dt < now:
                    parsed_dt += timedelta(days=1)

            parsed["due_datetime"] = parsed_dt  # ✅ real datetime object
            parsed["due_datetime_str"] = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")

            print("✅ LLM Extracted Task Entities:", parsed)
            return parsed

        except Exception as e:
            print("⚠️ LLM task extraction failed:", e)
            fallback_dt = datetime.now() + timedelta(hours=1)
            return {
                "task_title": "",
                "due_datetime": fallback_dt,
                "due_datetime_str": fallback_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "action": "",
                "context": "",
            }

    # ----------------- Convert Dates/Times ----------------- #
    def _convert_task_dates(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Converts extracted date/time strings to proper datetimes."""
        now = datetime.now()
        due_date = None
        due_time = None

        try:
            if task_data.get("due_date"):
                due_date = date_parser.parse(task_data["due_date"], fuzzy=True)
            if task_data.get("due_time"):
                due_time = date_parser.parse(task_data["due_time"], fuzzy=True)
        except Exception:
            pass

        # Handle missing cases
        if not due_date and due_time:
            due_date = due_time.date()

        if not due_date:
            due_date = now.date()
        if due_time and due_time.time() <= now.time():
            # If time already passed, set for tomorrow
            due_date = now.date() + timedelta(days=1)

        # Merge into a single datetime if both exist
        combined_dt = datetime.combine(due_date, due_time.time()) if due_time else datetime.combine(due_date, datetime.min.time())
        task_data["due_datetime"] = combined_dt.isoformat()

        return task_data
