# import os
# import re
# import spacy
# import json
# import google.generativeai as genai
# from typing import Dict, Any, Optional
# from datetime import datetime, timedelta
# from sentence_transformers import SentenceTransformer
# from dateutil import parser as date_parser
# import dateparser
# import calendar



# # ----------------- Embedding Helper ----------------- #
# embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# def generate_embedding(text: str):
#     """Generate normalized sentence embeddings."""
#     if not text or not text.strip():
#         return []
#     embedding = embedding_model.encode([text], normalize_embeddings=True)
#     return embedding[0].tolist()


# # ----------------- Intent Detector ----------------- #
# class IntentDetector:
#     """
#     Detects user intent and entities using explicit @commands,
#     rule-based logic, NER, and selectively calls LLM
#     for complex message types like send/reply/task/reminder.
#     """

#     def __init__(self, api_key: Optional[str] = None):
#         self.api_key = api_key or os.getenv("GEMINI_API_KEY")
#         genai.configure(api_key=self.api_key)
#         self.model = genai.GenerativeModel("gemini-2.5-flash")

#         # Load spaCy NER model
#         try:
#             self.nlp = spacy.load("en_core_web_sm")
#         except OSError:
#             raise ValueError("Please install spaCy model: python -m spacy download en_core_web_sm")

#         # Command mapping
#         self.command_map = {
#             "@read": "read_email",
#             "@find": "find_email",
#             "@send": "send_email",
#             "@reply": "reply_email",
#             "@summarize": "summarize_email",
#             "@task": "create_task",
#             "@meeting": "find_meeting",
#             "@doc": "find_document",
#             "@remind": "set_reminder",
#         }

#         # Keyword intent hints
#         self.intent_keywords = {
#             "read_email": ["read", "open"],
#             "find_email": ["email", "mail", "inbox"],
#             "send_email": ["send", "compose", "email"],
#             "reply_email": ["reply", "respond"],
#             "summarize_email": ["summarize", "summary"],
#             "create_task": ["task", "todo", "schedule"],
#             "set_reminder": ["remind", "remember", "by", "at", "in"],
#             "find_meeting": ["meeting", "calendar"],
#             "find_document": ["document", "file", "doc"],
#         }

#     # ----------------- Detect Intent ----------------- #
#     def detect_intent(self, message: str, previous_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
#         """Main entry point to detect intent and extract structured entities."""
#         message_lower = message.lower().strip()

#         # 1️⃣ Explicit command check
#         cmd_match = re.search(r"(@\w+)", message_lower)
#         if cmd_match:
#             command = cmd_match.group(1)
#             if command in self.command_map:
#                 intent = self.command_map[command]
#                 entities = self._extract_entities(message)


#                 # Use LLM for structured extraction
#                 if intent in ["send_email", "reply_email"]:
#                     entities.update(self._extract_send_reply_entities_with_llm(message))
#                 elif intent in ["create_task", "set_reminder"]:
#                     entities.update(self._extract_task_entities_with_llm(message))
#                     entities["input_text"] = message  # Preserve original text

#                 return {
#                     "intent": intent,
#                     "confidence": 1.0,
#                     "entities": entities,
#                     "source": "command",
#                 }

#         # 2️⃣ Rule-based fallback
#         result = self._detect_with_rules_and_ner(message)
#         intent = result["intent"]


#         if intent in ["send_email", "reply_email"]:
#             result["entities"].update(self._extract_send_reply_entities_with_llm(message))
#         elif intent in ["create_task", "set_reminder"]:
#             result["entities"].update(self._extract_task_entities_with_llm(message))
#             result["entities"]["input_text"] = message  # Preserve original text

#         return result

#     # ----------------- Rules + NER ----------------- #
#     def _detect_with_rules_and_ner(self, message: str) -> Dict[str, Any]:
#         """Uses keyword matching and NER to guess intent."""
#         message_lower = message.lower()
#         intent = "unknown"
#         confidence = 0.0
#         best_match = 0

#         for possible_intent, keywords in self.intent_keywords.items():
#             matches = sum(1 for kw in keywords if kw in message_lower)
#             if matches > best_match:
#                 best_match = matches
#                 intent = possible_intent
#                 confidence = min(1.0, matches / len(keywords))

#         entities = self._extract_entities(message)
#         return {
#             "intent": intent,
#             "confidence": confidence,
#             "entities": entities,
#             "source": "rules_ner",
#         }

#         # ----------------- Entity Extraction ----------------- #
#     def _extract_entities(self, message: str) -> Dict[str, str]:
#             """Extracts sender, org, and timeframe (converted to actual date if possible)."""
#             entities = {}
#             doc = self.nlp(message)
#             message_lower = message.lower()

#             # Extract named entities
#             for ent in doc.ents:
#                 if ent.label_ in ["PERSON", "ORG"] and "sender" not in entities:
#                     entities["sender"] = ent.text
#                 elif ent.label_ == "DATE" and "timeframe" not in entities:
#                     entities["timeframe"] = ent.text

#             # Regex fallback for sender
#             if "sender" not in entities:
#                 match_sender = re.search(r"from\s+([A-Za-z0-9&.\s]+)", message)
#                 if match_sender:
#                     entities["sender"] = match_sender.group(1).strip()

#             # Detect timeframe manually if not found
#             if "timeframe" not in entities:
#                 if "today" in message_lower:
#                     entities["timeframe"] = "today"
#                 elif "yesterday" in message_lower:
#                     entities["timeframe"] = "yesterday"
#                 elif "tomorrow" in message_lower:
#                     entities["timeframe"] = "tomorrow"
#                 elif "last week" in message_lower:
#                     entities["timeframe"] = "last week"
#                 elif "this week" in message_lower:
#                     entities["timeframe"] = "this week"
#                 elif "last month" in message_lower:
#                     entities["timeframe"] = "last month"

#             # Convert timeframe to actual date or range
#             if "timeframe" in entities:
#                 now = datetime.now()
#                 tf = entities["timeframe"].lower()

#                 if tf == "today":
#                     entities["timeframe"] = now.strftime("%Y-%m-%d")
#                 elif tf == "yesterday":
#                     entities["timeframe"] = (now - timedelta(days=1)).strftime("%Y-%m-%d")
#                 elif tf == "tomorrow":
#                     entities["timeframe"] = (now + timedelta(days=1)).strftime("%Y-%m-%d")
#                 elif tf == "last week":
#                     start = now - timedelta(days=now.weekday() + 7)
#                     end = start + timedelta(days=6)
#                     entities["timeframe"] = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
#                 elif tf == "this week":
#                     start = now - timedelta(days=now.weekday())
#                     end = start + timedelta(days=6)
#                     entities["timeframe"] = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
#                 elif tf == "last month":
#                     first_day_this_month = now.replace(day=1)
#                     last_day_last_month = first_day_this_month - timedelta(days=1)
#                     start_last_month = last_day_last_month.replace(day=1)
#                     entities["timeframe"] = f"{start_last_month.strftime('%Y-%m-%d')} to {last_day_last_month.strftime('%Y-%m-%d')}"

#             # Always include query text
#             if message.strip():
#                 entities["query_text"] = message.strip()

#             return entities

#     # ----------------- Email Entity Extraction via LLM ----------------- #
#     def _extract_send_reply_entities_with_llm(self, message: str) -> Dict[str, Any]:
#         """Extract recipient, subject, and email body using LLM."""
#         llm_prompt = f"""
#         You are Whispr, an AI email assistant.
#         Extract structured email details from this message.

#         Message: "{message}"

#         Return only valid JSON:
#         {{
#             "receiver_name": "<name or empty>",
#             "receiver_email": "<email if available>",
#             "subject": "<generate subject if not provided>",
#             "body": "<generate a clear and polite email body>"
#         }}
#         """
#         try:
#             response = self.model.generate_content(llm_prompt)
#             raw = response.text.strip()
#             cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
#             parsed = json.loads(cleaned)
#             return parsed
#         except Exception as e:
#             print("⚠️ LLM email extraction failed:", e)
#             return {"receiver_name": "", "receiver_email": "", "subject": "", "body": ""}

#         # ----------------- Task Entity Extraction via LLM ----------------- #
#     def _extract_task_entities_with_llm(self, message: str) -> Dict[str, Any]:
#         llm_prompt = f"""
#         You are Whispr, an AI assistant that manages tasks and reminders.
#         Extract structured task information from the user's message.

#         Message: "{message}"

#         Return only valid JSON:
#         {{
#             "task_type": "<type of task or reminder list: email_send, reply, reminder, summarize, watch_incoming_emails>",
#             "task_title": "<short summary of the task>",
#             "due_time": "<specific time or datetime if mentioned, else empty>",
#             "due_date": "<specific date if mentioned, else empty>",
#             "action": "<type of action list: email_send, reply, reminder, summarize, watch_incoming_emails>",
#             "context": "<extra context or who/what it's about>"
#         }}
#         """

#         try:
#             response = self.model.generate_content(llm_prompt)
#             raw = response.text.strip()
#             cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
#             parsed = json.loads(cleaned)

#             # ---------------- Date/Time Normalization ----------------
#             now = datetime.now()
#             due_time_str = parsed.get("due_time", "").strip()
#             due_date_str = parsed.get("due_date", "").strip()

#             # Combine the date and time for parsing
#             combined_text = f"{due_date_str} {due_time_str}".strip()
#             parsed_dt = dateparser.parse(combined_text, settings={"RELATIVE_BASE": now})
#             print("Parsed datetime:", parsed_dt)

#             # Default logic
#             if not parsed_dt:
#                 # Try parsing only time
#                 if due_time_str:
#                     time_only = dateparser.parse(due_time_str, settings={"RELATIVE_BASE": now})
#                     if time_only:
#                         parsed_dt = datetime.combine(now.date(), time_only.time())
#                         # If that time already passed, move to tomorrow
#                         if parsed_dt < now:
#                             parsed_dt += timedelta(days=1)
#                 # If nothing, default to 1 hour later
#                 if not parsed_dt:
#                     parsed_dt = now + timedelta(hours=1)
#             else:
#                 # If the parsed date/time is in the past, roll forward one day
#                 if parsed_dt < now:
#                     parsed_dt += timedelta(days=1)

#             parsed["due_datetime"] = parsed_dt  # ✅ real datetime object
#             parsed["due_datetime_str"] = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")

#             return parsed

#         except Exception as e:
#             print("⚠️ LLM task extraction failed:", e)
#             fallback_dt = datetime.now() + timedelta(hours=1)
#             return {
#                 "task_title": "",
#                 "due_datetime": fallback_dt,
#                 "due_datetime_str": fallback_dt.strftime("%Y-%m-%d %H:%M:%S"),
#                 "action": "",
#                 "context": "",
#             }

#     # ----------------- Convert Dates/Times ----------------- #
#     def _convert_task_dates(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
#         """Converts extracted date/time strings to proper datetimes."""
#         now = datetime.now()
#         due_date = None
#         due_time = None

#         try:
#             if task_data.get("due_date"):
#                 due_date = date_parser.parse(task_data["due_date"], fuzzy=True)
#             if task_data.get("due_time"):
#                 due_time = date_parser.parse(task_data["due_time"], fuzzy=True)
#         except Exception:
#             pass

#         # Handle missing cases
#         if not due_date and due_time:
#             due_date = due_time.date()

#         if not due_date:
#             due_date = now.date()
#         if due_time and due_time.time() <= now.time():
#             # If time already passed, set for tomorrow
#             due_date = now.date() + timedelta(days=1)

#         # Merge into a single datetime if both exist
#         combined_dt = datetime.combine(due_date, due_time.time()) if due_time else datetime.combine(due_date, datetime.min.time())
#         task_data["due_datetime"] = combined_dt.isoformat()

#         return task_data



# intent_detector.py

import os, re, json, spacy, google.generativeai as genai
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import dateparser
from dateutil import parser as date_parser
from .retriever import retrieve_relevant_items  # 👈 integrated retriever


# ----------------- Embedding Helper ----------------- #
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def generate_embedding(text: str):
    """Generate normalized embeddings for any text."""
    if not text or not text.strip():
        return []
    embedding = embedding_model.encode([text], normalize_embeddings=True)
    return embedding[0].tolist()


# ----------------- Intent Detector ----------------- #
class IntentDetector:
    """
    Detects user intent and entities across channels (email, whatsapp, slack, etc.)
    Also retrieves recent contextual messages or emails if relevant.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            raise ValueError("Run: python -m spacy download en_core_web_sm")

        # Explicit command shortcuts
        self.command_map = {
            "@read": "read_message",
            "@find": "find_message",
            "@send": "send_message",
            "@reply": "reply_message",
            "@summarize": "summarize_message",
            "@task": "create_task",
            "@remind": "set_reminder",
        }

        # Intent keyword patterns
        self.intent_keywords = {
            "read_message": ["read", "open"],
            "find_message": ["message", "chat", "email", "conversation"],
            "send_message": ["send", "compose", "write"],
            "reply_message": ["reply", "respond"],
            "summarize_message": ["summarize", "summary"],
            "create_task": ["task", "todo", "schedule"],
            "set_reminder": ["remind", "remember", "by", "at", "in"],
        }

    # ----------------- MAIN ----------------- #
    def detect_intent(
        self, user, message: str, channel: Optional[str] = None, previous_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detects user intent, auto-detects communication channel, extracts entities,
        and retrieves relevant contextual data (emails, chats, etc.).
        """
        message_lower = message.lower().strip()

        # 🔹 Auto-detect communication channel
        if not channel:
            if any(word in message_lower for word in ["email", "inbox", "gmail", "subject"]):
                channel = "email"
            elif any(word in message_lower for word in ["whatsapp", "chat", "dm", "text"]):
                channel = "whatsapp"
            elif any(word in message_lower for word in ["slack", "workspace", "mention"]):
                channel = "slack"
            else:
                channel = "all"

        # 🔹 Handle explicit @commands first
        cmd_match = re.search(r"(@\w+)", message_lower)
        if cmd_match:
            command = cmd_match.group(1)
            if command in self.command_map:
                intent = self.command_map[command]
                entities = self._extract_entities(message, channel)

                if intent in ["send_message", "reply_message"]:
                    entities.update(self._extract_send_entities_with_llm(message, channel))
                elif intent in ["create_task", "set_reminder"]:
                    entities.update(self._extract_task_entities_with_llm(message))
                    entities["input_text"] = message

                # 🔹 Retrieve related context
                relevant = retrieve_relevant_items(user, message, channel)

                return {
                    "intent": intent,
                    "confidence": 1.0,
                    "entities": entities,
                    "source": "command",
                    "channel": channel,
                    "relevant": {
                        "channel": channel,
                        "items": self._format_relevant(relevant),
                    },
                }

        # 🔹 Otherwise, detect with rules + NER
        result = self._detect_with_rules_and_ner(message, channel)
        intent = result["intent"]

        if intent in ["send_message", "reply_message"]:
            result["entities"].update(self._extract_send_entities_with_llm(message, channel))
        elif intent in ["create_task", "set_reminder"]:
            result["entities"].update(self._extract_task_entities_with_llm(message))
            result["entities"]["input_text"] = message

        # 🔹 Retrieve related content (emails, chats)
        relevant = retrieve_relevant_items(user, message, channel)

        return {
            **result,
            "channel": channel,
            "relevant": {
                "channel": channel,
                "items": self._format_relevant(relevant),
            },
        }

    # ----------------- RULES + NER ----------------- #
    def _detect_with_rules_and_ner(self, message: str, channel: str) -> Dict[str, Any]:
        """Rule-based keyword + NER approach for general message understanding."""
        message_lower = message.lower()
        intent, confidence, best_match = "unknown", 0.0, 0

        for possible_intent, keywords in self.intent_keywords.items():
            matches = sum(1 for kw in keywords if kw in message_lower)
            if matches > best_match:
                best_match = matches
                intent = possible_intent
                confidence = min(1.0, matches / len(keywords))

        entities = self._extract_entities(message, channel)
        return {
            "intent": intent,
            "confidence": confidence,
            "entities": entities,
            "source": "rules_ner",
        }

    # ----------------- ENTITY EXTRACTION ----------------- #
    def _extract_entities(self, message: str, channel: str) -> Dict[str, str]:
        """Extract sender, org, timeframe, etc., based on channel type."""
        entities = {}
        doc = self.nlp(message)

        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG"] and "sender" not in entities:
                entities["sender"] = ent.text
            elif ent.label_ == "DATE" and "timeframe" not in entities:
                entities["timeframe"] = ent.text

        if "sender" not in entities:
            match_sender = re.search(r"from\s+([A-Za-z0-9&.\s]+)", message)
            if match_sender:
                entities["sender"] = match_sender.group(1).strip()

        parsed_time = dateparser.parse(message, settings={"RELATIVE_BASE": datetime.now()})
        if parsed_time:
            entities["parsed_time"] = parsed_time.strftime("%Y-%m-%d %H:%M")

        entities["has_subject"] = channel == "email"
        if message.strip():
            entities["query_text"] = message.strip()

        return entities

    # ----------------- SEND ENTITY EXTRACTION (LLM) ----------------- #
    def _extract_send_entities_with_llm(self, message: str, channel: str) -> Dict[str, Any]:
        channel_prompt = {
            "email": "Extract receiver, subject, and body.",
            "whatsapp": "Extract recipient name and message body (no subject).",
            "slack": "Extract channel, mentions, and message body.",
        }

        llm_prompt = f"""
        You are Whispr, an AI assistant handling {channel} messages.
        {channel_prompt.get(channel, 'Extract message details clearly.')}

        Message: "{message}"

        Return valid JSON:
        {{
            "receiver_name": "<name>",
            "receiver_identifier": "<email/phone/channel>",
            "subject": "<if applicable>",
            "body": "<message body>"
        }}
        """

        try:
            response = self.model.generate_content(llm_prompt)
            raw = response.text.strip()
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
            return json.loads(cleaned)
        except Exception as e:
            print("⚠️ LLM send entity extraction failed:", e)
            return {"receiver_name": "", "receiver_identifier": "", "subject": "", "body": ""}

    # ----------------- TASK ENTITY EXTRACTION (LLM) ----------------- #
    def _extract_task_entities_with_llm(self, message: str) -> Dict[str, Any]:
        llm_prompt = f"""
        You are Whispr, an AI assistant that manages tasks and reminders.
        Extract structured task info from this message.

        Message: "{message}"

        Return only valid JSON:
        {{
            "task_type": "<type>",
            "task_title": "<short summary>",
            "due_time": "<specific time if mentioned>",
            "due_date": "<specific date if mentioned>",
            "action": "<action type>",
            "context": "<context or who/what it's about>"
        }}
        """
        try:
            response = self.model.generate_content(llm_prompt)
            raw = response.text.strip()
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
            parsed = json.loads(cleaned)

            now = datetime.now()
            combined_text = f"{parsed.get('due_date', '')} {parsed.get('due_time', '')}".strip()
            parsed_dt = dateparser.parse(combined_text, settings={"RELATIVE_BASE": now})

            if not parsed_dt or parsed_dt < now:
                parsed_dt = now + timedelta(hours=1)

            parsed["due_datetime"] = parsed_dt
            parsed["due_datetime_str"] = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
            return parsed
        except Exception as e:
            print("⚠️ LLM task extraction failed:", e)
            fallback = datetime.now() + timedelta(hours=1)
            return {
                "task_title": "",
                "due_datetime": fallback,
                "due_datetime_str": fallback.strftime("%Y-%m-%d %H:%M:%S"),
                "action": "",
                "context": "",
            }

    # ----------------- FORMATTER ----------------- #
    def _format_relevant(self, items):
        """Convert ORM objects to safe serializable dicts."""
        formatted = []
        for obj in items:
            snippet = getattr(obj, "snippet", None) or getattr(obj, "body", "")[:120]
            date_field = getattr(obj, "received_at", None) or getattr(obj, "created_at", None)
            formatted.append({
                "id": getattr(obj, "id", None),
                "snippet": snippet,
                "date": date_field.strftime("%Y-%m-%d %H:%M") if date_field else None,
                "sender": getattr(obj, "sender", None) or getattr(obj, "from_user", None),
            })
        return formatted
