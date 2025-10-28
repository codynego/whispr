# # import os
# # import re
# # import spacy
# # import json
# # import google.generativeai as genai
# # from typing import Dict, Any, Optional
# # from datetime import datetime, timedelta
# # from sentence_transformers import SentenceTransformer
# # from dateutil import parser as date_parser
# # import dateparser
# # import calendar



# # # ----------------- Embedding Helper ----------------- #
# # embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# # def generate_embedding(text: str):
# #     """Generate normalized sentence embeddings."""
# #     if not text or not text.strip():
# #         return []
# #     embedding = embedding_model.encode([text], normalize_embeddings=True)
# #     return embedding[0].tolist()


# # # ----------------- Intent Detector ----------------- #
# # class IntentDetector:
# #     """
# #     Detects user intent and entities using explicit @commands,
# #     rule-based logic, NER, and selectively calls LLM
# #     for complex message types like send/reply/task/reminder.
# #     """

# #     def __init__(self, api_key: Optional[str] = None):
# #         self.api_key = api_key or os.getenv("GEMINI_API_KEY")
# #         genai.configure(api_key=self.api_key)
# #         self.model = genai.GenerativeModel("gemini-2.5-flash")

# #         # Load spaCy NER model
# #         try:
# #             self.nlp = spacy.load("en_core_web_sm")
# #         except OSError:
# #             raise ValueError("Please install spaCy model: python -m spacy download en_core_web_sm")

# #         # Command mapping
# #         self.command_map = {
# #             "@read": "read_email",
# #             "@find": "find_email",
# #             "@send": "send_email",
# #             "@reply": "reply_email",
# #             "@summarize": "summarize_email",
# #             "@task": "create_task",
# #             "@meeting": "find_meeting",
# #             "@doc": "find_document",
# #             "@remind": "set_reminder",
# #         }

# #         # Keyword intent hints
# #         self.intent_keywords = {
# #             "read_email": ["read", "open"],
# #             "find_email": ["email", "mail", "inbox"],
# #             "send_email": ["send", "compose", "email"],
# #             "reply_email": ["reply", "respond"],
# #             "summarize_email": ["summarize", "summary"],
# #             "create_task": ["task", "todo", "schedule"],
# #             "set_reminder": ["remind", "remember", "by", "at", "in"],
# #             "find_meeting": ["meeting", "calendar"],
# #             "find_document": ["document", "file", "doc"],
# #         }

# #     # ----------------- Detect Intent ----------------- #
# #     def detect_intent(self, message: str, previous_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
# #         """Main entry point to detect intent and extract structured entities."""
# #         message_lower = message.lower().strip()

# #         # 1️⃣ Explicit command check
# #         cmd_match = re.search(r"(@\w+)", message_lower)
# #         if cmd_match:
# #             command = cmd_match.group(1)
# #             if command in self.command_map:
# #                 intent = self.command_map[command]
# #                 entities = self._extract_entities(message)


# #                 # Use LLM for structured extraction
# #                 if intent in ["send_email", "reply_email"]:
# #                     entities.update(self._extract_send_reply_entities_with_llm(message))
# #                 elif intent in ["create_task", "set_reminder"]:
# #                     entities.update(self._extract_task_entities_with_llm(message))
# #                     entities["input_text"] = message  # Preserve original text

# #                 return {
# #                     "intent": intent,
# #                     "confidence": 1.0,
# #                     "entities": entities,
# #                     "source": "command",
# #                 }

# #         # 2️⃣ Rule-based fallback
# #         result = self._detect_with_rules_and_ner(message)
# #         intent = result["intent"]


# #         if intent in ["send_email", "reply_email"]:
# #             result["entities"].update(self._extract_send_reply_entities_with_llm(message))
# #         elif intent in ["create_task", "set_reminder"]:
# #             result["entities"].update(self._extract_task_entities_with_llm(message))
# #             result["entities"]["input_text"] = message  # Preserve original text

# #         return result

# #     # ----------------- Rules + NER ----------------- #
# #     def _detect_with_rules_and_ner(self, message: str) -> Dict[str, Any]:
# #         """Uses keyword matching and NER to guess intent."""
# #         message_lower = message.lower()
# #         intent = "unknown"
# #         confidence = 0.0
# #         best_match = 0

# #         for possible_intent, keywords in self.intent_keywords.items():
# #             matches = sum(1 for kw in keywords if kw in message_lower)
# #             if matches > best_match:
# #                 best_match = matches
# #                 intent = possible_intent
# #                 confidence = min(1.0, matches / len(keywords))

# #         entities = self._extract_entities(message)
# #         return {
# #             "intent": intent,
# #             "confidence": confidence,
# #             "entities": entities,
# #             "source": "rules_ner",
# #         }

# #         # ----------------- Entity Extraction ----------------- #
# #     def _extract_entities(self, message: str) -> Dict[str, str]:
# #             """Extracts sender, org, and timeframe (converted to actual date if possible)."""
# #             entities = {}
# #             doc = self.nlp(message)
# #             message_lower = message.lower()

# #             # Extract named entities
# #             for ent in doc.ents:
# #                 if ent.label_ in ["PERSON", "ORG"] and "sender" not in entities:
# #                     entities["sender"] = ent.text
# #                 elif ent.label_ == "DATE" and "timeframe" not in entities:
# #                     entities["timeframe"] = ent.text

# #             # Regex fallback for sender
# #             if "sender" not in entities:
# #                 match_sender = re.search(r"from\s+([A-Za-z0-9&.\s]+)", message)
# #                 if match_sender:
# #                     entities["sender"] = match_sender.group(1).strip()

# #             # Detect timeframe manually if not found
# #             if "timeframe" not in entities:
# #                 if "today" in message_lower:
# #                     entities["timeframe"] = "today"
# #                 elif "yesterday" in message_lower:
# #                     entities["timeframe"] = "yesterday"
# #                 elif "tomorrow" in message_lower:
# #                     entities["timeframe"] = "tomorrow"
# #                 elif "last week" in message_lower:
# #                     entities["timeframe"] = "last week"
# #                 elif "this week" in message_lower:
# #                     entities["timeframe"] = "this week"
# #                 elif "last month" in message_lower:
# #                     entities["timeframe"] = "last month"

# #             # Convert timeframe to actual date or range
# #             if "timeframe" in entities:
# #                 now = datetime.now()
# #                 tf = entities["timeframe"].lower()

# #                 if tf == "today":
# #                     entities["timeframe"] = now.strftime("%Y-%m-%d")
# #                 elif tf == "yesterday":
# #                     entities["timeframe"] = (now - timedelta(days=1)).strftime("%Y-%m-%d")
# #                 elif tf == "tomorrow":
# #                     entities["timeframe"] = (now + timedelta(days=1)).strftime("%Y-%m-%d")
# #                 elif tf == "last week":
# #                     start = now - timedelta(days=now.weekday() + 7)
# #                     end = start + timedelta(days=6)
# #                     entities["timeframe"] = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
# #                 elif tf == "this week":
# #                     start = now - timedelta(days=now.weekday())
# #                     end = start + timedelta(days=6)
# #                     entities["timeframe"] = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
# #                 elif tf == "last month":
# #                     first_day_this_month = now.replace(day=1)
# #                     last_day_last_month = first_day_this_month - timedelta(days=1)
# #                     start_last_month = last_day_last_month.replace(day=1)
# #                     entities["timeframe"] = f"{start_last_month.strftime('%Y-%m-%d')} to {last_day_last_month.strftime('%Y-%m-%d')}"

# #             # Always include query text
# #             if message.strip():
# #                 entities["query_text"] = message.strip()

# #             return entities

# #     # ----------------- Email Entity Extraction via LLM ----------------- #
# #     def _extract_send_reply_entities_with_llm(self, message: str) -> Dict[str, Any]:
# #         """Extract recipient, subject, and email body using LLM."""
# #         llm_prompt = f"""
# #         You are Whispr, an AI email assistant.
# #         Extract structured email details from this message.

# #         Message: "{message}"

# #         Return only valid JSON:
# #         {{
# #             "receiver_name": "<name or empty>",
# #             "receiver_email": "<email if available>",
# #             "subject": "<generate subject if not provided>",
# #             "body": "<generate a clear and polite email body>"
# #         }}
# #         """
# #         try:
# #             response = self.model.generate_content(llm_prompt)
# #             raw = response.text.strip()
# #             cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
# #             parsed = json.loads(cleaned)
# #             return parsed
# #         except Exception as e:
# #             print("⚠️ LLM email extraction failed:", e)
# #             return {"receiver_name": "", "receiver_email": "", "subject": "", "body": ""}

# #         # ----------------- Task Entity Extraction via LLM ----------------- #
# #     def _extract_task_entities_with_llm(self, message: str) -> Dict[str, Any]:
# #         llm_prompt = f"""
# #         You are Whispr, an AI assistant that manages tasks and reminders.
# #         Extract structured task information from the user's message.

# #         Message: "{message}"

# #         Return only valid JSON:
# #         {{
# #             "task_type": "<type of task or reminder list: email_send, reply, reminder, summarize, watch_incoming_emails>",
# #             "task_title": "<short summary of the task>",
# #             "due_time": "<specific time or datetime if mentioned, else empty>",
# #             "due_date": "<specific date if mentioned, else empty>",
# #             "action": "<type of action list: email_send, reply, reminder, summarize, watch_incoming_emails>",
# #             "context": "<extra context or who/what it's about>"
# #         }}
# #         """

# #         try:
# #             response = self.model.generate_content(llm_prompt)
# #             raw = response.text.strip()
# #             cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
# #             parsed = json.loads(cleaned)

# #             # ---------------- Date/Time Normalization ----------------
# #             now = datetime.now()
# #             due_time_str = parsed.get("due_time", "").strip()
# #             due_date_str = parsed.get("due_date", "").strip()

# #             # Combine the date and time for parsing
# #             combined_text = f"{due_date_str} {due_time_str}".strip()
# #             parsed_dt = dateparser.parse(combined_text, settings={"RELATIVE_BASE": now})
# #             print("Parsed datetime:", parsed_dt)

# #             # Default logic
# #             if not parsed_dt:
# #                 # Try parsing only time
# #                 if due_time_str:
# #                     time_only = dateparser.parse(due_time_str, settings={"RELATIVE_BASE": now})
# #                     if time_only:
# #                         parsed_dt = datetime.combine(now.date(), time_only.time())
# #                         # If that time already passed, move to tomorrow
# #                         if parsed_dt < now:
# #                             parsed_dt += timedelta(days=1)
# #                 # If nothing, default to 1 hour later
# #                 if not parsed_dt:
# #                     parsed_dt = now + timedelta(hours=1)
# #             else:
# #                 # If the parsed date/time is in the past, roll forward one day
# #                 if parsed_dt < now:
# #                     parsed_dt += timedelta(days=1)

# #             parsed["due_datetime"] = parsed_dt  # ✅ real datetime object
# #             parsed["due_datetime_str"] = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")

# #             return parsed

# #         except Exception as e:
# #             print("⚠️ LLM task extraction failed:", e)
# #             fallback_dt = datetime.now() + timedelta(hours=1)
# #             return {
# #                 "task_title": "",
# #                 "due_datetime": fallback_dt,
# #                 "due_datetime_str": fallback_dt.strftime("%Y-%m-%d %H:%M:%S"),
# #                 "action": "",
# #                 "context": "",
# #             }

# #     # ----------------- Convert Dates/Times ----------------- #
# #     def _convert_task_dates(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
# #         """Converts extracted date/time strings to proper datetimes."""
# #         now = datetime.now()
# #         due_date = None
# #         due_time = None

# #         try:
# #             if task_data.get("due_date"):
# #                 due_date = date_parser.parse(task_data["due_date"], fuzzy=True)
# #             if task_data.get("due_time"):
# #                 due_time = date_parser.parse(task_data["due_time"], fuzzy=True)
# #         except Exception:
# #             pass

# #         # Handle missing cases
# #         if not due_date and due_time:
# #             due_date = due_time.date()

# #         if not due_date:
# #             due_date = now.date()
# #         if due_time and due_time.time() <= now.time():
# #             # If time already passed, set for tomorrow
# #             due_date = now.date() + timedelta(days=1)

# #         # Merge into a single datetime if both exist
# #         combined_dt = datetime.combine(due_date, due_time.time()) if due_time else datetime.combine(due_date, datetime.min.time())
# #         task_data["due_datetime"] = combined_dt.isoformat()

# #         return task_data



# # intent_detector.py

# import os, re, json, spacy, google.generativeai as genai
# from datetime import datetime, timedelta
# from typing import Dict, Any, Optional
# from sentence_transformers import SentenceTransformer
# import dateparser
# from dateutil import parser as date_parser
# from whisprai.ai.retriever import retrieve_relevant_messages


# # ----------------- Embedding Helper ----------------- #
# embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# def generate_embedding(text: str):
#     """Generate normalized embeddings for any text."""
#     if not text or not text.strip():
#         return []
#     embedding = embedding_model.encode([text], normalize_embeddings=True)
#     return embedding[0].tolist()


# # ----------------- Intent Detector ----------------- #
# class IntentDetector:
#     """
#     Detects user intent and entities across channels (email, whatsapp, slack, etc.)
#     Also retrieves recent contextual messages or emails if relevant.
#     """

#     def __init__(self, api_key: Optional[str] = None):
#         self.api_key = api_key or os.getenv("GEMINI_API_KEY")
#         genai.configure(api_key=self.api_key)
#         self.model = genai.GenerativeModel("gemini-2.5-flash")

#         try:
#             self.nlp = spacy.load("en_core_web_sm")
#         except OSError:
#             raise ValueError("Run: python -m spacy download en_core_web_sm")

#         # Explicit command shortcuts
#         self.command_map = {
#             "@read": "read_message",
#             "@find": "find_message",
#             "@send": "send_message",
#             "@reply": "reply_message",
#             "@summarize": "summarize_message",
#             "@task": "create_task",
#             "@remind": "set_reminder",
#         }

#         # Intent keyword patterns
#         self.intent_keywords = {
#             "read_message": ["read", "open"],
#             "find_message": ["message", "chat", "email", "conversation"],
#             "send_message": ["send", "compose", "write"],
#             "reply_message": ["reply", "respond"],
#             "summarize_message": ["summarize", "summary"],
#             "create_task": ["task", "todo", "schedule"],
#             "set_reminder": ["remind", "remember", "by", "at", "in"],
#         }

#     # ----------------- MAIN ----------------- #
#     def detect_intent(
#         self, user, message: str, channel: Optional[str] = None, previous_context: Optional[Dict[str, Any]] = None
#     ) -> Dict[str, Any]:
#         """
#         Detects user intent, auto-detects communication channel, extracts entities,
#         and retrieves relevant contextual data (emails, chats, etc.).
#         """
#         message_lower = message.lower().strip()

#         # 🔹 Auto-detect communication channel
#         if not channel:
#             if any(word in message_lower for word in ["email", "inbox", "gmail", "subject"]):
#                 channel = "email"
#             elif any(word in message_lower for word in ["whatsapp", "chat", "dm", "text"]):
#                 channel = "whatsapp"
#             elif any(word in message_lower for word in ["slack", "workspace", "mention"]):
#                 channel = "slack"
#             else:
#                 channel = "all"

#         # 🔹 Handle explicit @commands first
#         cmd_match = re.search(r"(@\w+)", message_lower)
#         if cmd_match:
#             command = cmd_match.group(1)
#             if command in self.command_map:
#                 intent = self.command_map[command]
#                 entities = self._extract_entities(message, channel)

#                 if intent in ["send_message", "reply_message"]:
#                     entities.update(self._extract_send_entities_with_llm(message, channel))
#                 elif intent in ["create_task", "set_reminder"]:
#                     entities.update(self._extract_task_entities_with_llm(message))
#                     entities["input_text"] = message

#                 # 🔹 Retrieve related context
#                 # relevant = retrieve_relevant_messages(user, message, channel)

#                 return {
#                     "intent": intent,
#                     "confidence": 1.0,
#                     "entities": entities,
#                     "source": "command",
#                     "channel": channel,
#                 }

#         # 🔹 Otherwise, detect with rules + NER
#         result = self._detect_with_rules_and_ner(message, channel)
#         intent = result["intent"]

#         if intent in ["send_message", "reply_message"]:
#             result["entities"].update(self._extract_send_entities_with_llm(message, channel))
#         elif intent in ["create_task", "set_reminder"]:
#             result["entities"].update(self._extract_task_entities_with_llm(message))
#             result["entities"]["input_text"] = message

#         # 🔹 Retrieve related content (emails, chats)
#         # relevant = retrieve_relevant_messages(user, message, channel)

#         return {
#             **result,
#             "channel": channel,
#         }

#     # ----------------- RULES + NER ----------------- #
#     def _detect_with_rules_and_ner(self, message: str, channel: str) -> Dict[str, Any]:
#         """Rule-based keyword + NER approach for general message understanding."""
#         message_lower = message.lower()
#         intent, confidence, best_match = "unknown", 0.0, 0

#         for possible_intent, keywords in self.intent_keywords.items():
#             matches = sum(1 for kw in keywords if kw in message_lower)
#             if matches > best_match:
#                 best_match = matches
#                 intent = possible_intent
#                 confidence = min(1.0, matches / len(keywords))

#         entities = self._extract_entities(message, channel)
#         return {
#             "intent": intent,
#             "confidence": confidence,
#             "entities": entities,
#             "source": "rules_ner",
#         }

#     # ----------------- ENTITY EXTRACTION ----------------- #
#     def _extract_entities(self, message: str, channel: str) -> Dict[str, str]:
#         """Extract sender, org, timeframe, etc., based on channel type."""
#         entities = {}
#         doc = self.nlp(message)

#         for ent in doc.ents:
#             if ent.label_ in ["PERSON", "ORG"] and "sender" not in entities:
#                 entities["sender"] = ent.text
#             elif ent.label_ == "DATE" and "timeframe" not in entities:
#                 entities["timeframe"] = ent.text

#         if "sender" not in entities:
#             match_sender = re.search(r"from\s+([A-Za-z0-9&.\s]+)", message)
#             if match_sender:
#                 entities["sender"] = match_sender.group(1).strip()

#         parsed_time = dateparser.parse(message, settings={"RELATIVE_BASE": datetime.now()})
#         if parsed_time:
#             entities["parsed_time"] = parsed_time.strftime("%Y-%m-%d %H:%M")

#         entities["has_subject"] = channel == "email"
#         if message.strip():
#             entities["query_text"] = message.strip()

#         return entities

#     # ----------------- SEND ENTITY EXTRACTION (LLM) ----------------- #
#     def _extract_send_entities_with_llm(self, message: str, channel: str) -> Dict[str, Any]:
#         channel_prompt = {
#             "email": "Extract receiver, subject, and body.",
#             "whatsapp": "Extract recipient name and message body (no subject).",
#             "slack": "Extract channel, mentions, and message body.",
#         }

#         llm_prompt = f"""
#         You are Whispr, an AI assistant handling {channel} messages.
#         {channel_prompt.get(channel, 'Extract message details clearly.')}

#         Message: "{message}"

#         Return valid JSON:
#         {{
#             "receiver_name": "<name gotten from either the message or email>",
#             "receiver": "<email/phone/channel>",
#             "subject": "<if applicable - generate one based on the message>",
#             "body": "<message body - write the body if not specified>"
#         }}
#         """

#         try:
#             response = self.model.generate_content(llm_prompt)
#             raw = response.text.strip()
#             cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
#             return json.loads(cleaned)
#         except Exception as e:
#             print("⚠️ LLM send entity extraction failed:", e)
#             return {"receiver_name": "", "receiver_identifier": "", "subject": "", "body": ""}

#     # ----------------- TASK ENTITY EXTRACTION (LLM) ----------------- #
#     def _extract_task_entities_with_llm(self, message: str) -> Dict[str, Any]:
#         llm_prompt = f"""
#         You are Whispr, an AI assistant that manages tasks and reminders.
#         Extract structured task info from this message.

#         Message: "{message}"

#         Return only valid JSON:
#         {{
#             "task_type": "<type>",
#             "task_title": "<a detailed report of the finished task - it should be as though you are giving a report to a human e.g "hey, i would like to remind you about your meeting with john tomorrow at 3pm, dont forget".>",
#             "due_time": "<specific time if mentioned>",
#             "due_date": "<specific date if mentioned>",
#             "action": "<action type>",
#             "context": "<context or who/what it's about>"
#         }}
#         """
#         try:
#             response = self.model.generate_content(llm_prompt)
#             raw = response.text.strip()
#             cleaned = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
#             parsed = json.loads(cleaned)

#             now = datetime.now()
#             combined_text = f"{parsed.get('due_date', '')} {parsed.get('due_time', '')}".strip()
#             parsed_dt = dateparser.parse(combined_text, settings={"RELATIVE_BASE": now})

#             if not parsed_dt or parsed_dt < now:
#                 parsed_dt = now + timedelta(hours=1)

#             parsed["due_datetime"] = parsed_dt
#             parsed["due_datetime_str"] = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
#             return parsed
#         except Exception as e:
#             print("⚠️ LLM task extraction failed:", e)
#             fallback = datetime.now() + timedelta(hours=1)
#             return {
#                 "task_title": "",
#                 "due_datetime": fallback,
#                 "due_datetime_str": fallback.strftime("%Y-%m-%d %H:%M:%S"),
#                 "action": "",
#                 "context": "",
#             }

#     # ----------------- FORMATTER ----------------- #
#     def _format_relevant(self, items):
#         """Convert ORM objects to safe serializable dicts."""
#         formatted = []
#         for obj in items:
#             snippet = getattr(obj, "snippet", None) or getattr(obj, "body", "")[:120]
#             date_field = getattr(obj, "received_at", None) or getattr(obj, "created_at", None)
#             formatted.append({
#                 "id": getattr(obj, "id", None),
#                 "snippet": snippet,
#                 "date": date_field.strftime("%Y-%m-%d %H:%M") if date_field else None,
#                 "sender": getattr(obj, "sender", None) or getattr(obj, "from_user", None),
#             })
#         return formatted



# intent_detector_gemini.py
import os
import re
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

import google.generativeai as genai
import dateparser
import spacy
from sentence_transformers import SentenceTransformer
from unified.models import Message
from django.conf import settings

from whisprai.ai.retriever import retrieve_relevant_messages  # your existing retriever
    # ----------------- Gemini calling ----------------- #
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# ----------------- Embedding Helper (kept for retrieval purposes) ----------------- #
_embedding_model = None
def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def generate_embedding(text: str):
    if not text or not text.strip():
        return []
    model = get_embedding_model()
    emb = model.encode([text], normalize_embeddings=True)
    return emb[0].tolist()

# ----------------- JSON safe parser fallback ----------------- #
def _safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Try robust JSON extraction from LLM output:
    - strip markdown fences
    - find first {...} block and load
    """
    if not text:
        return None
    # Remove triple backticks and language hints
    cleaned = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()

    # Try direct load
    try:
        return json.loads(cleaned)
    except Exception:
        # Attempt to locate the first JSON object substring
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start:end+1]
            try:
                return json.loads(candidate)
            except Exception as e:
                logger.debug("Failed to parse candidate JSON: %s", e)
                return None
    return None

# ----------------- IntentDetector (Gemini-first) ----------------- #
class IntentDetector:
    """
    Gemini-first intent detector.
    - Uses generative model (Gemini) to map free text -> structured JSON intent + entities.
    - Falls back to a light rule+NER extractor when the LLM fails or has low confidence.
    """

    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.GEMINI_MODEL)

        # spaCy for light NER fallback
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Raise a clear error instructing how to install
            raise RuntimeError("spacy model missing: run `python -m spacy download en_core_web_sm`")

        # lightweight intent keywords fallback (kept for robustness)
        self.intent_keywords = {
            "read_message": ["read", "open", "show"],
            "find_message": ["find", "search", "any email", "any message", "from"],
            "send_message": ["send", "compose", "email to", "message to"],
            "reply_message": ["reply", "respond"],
            "summarize_message": ["summarize", "summary", "sum up"],
            "create_task": ["task", "todo", "remind me to", "add task"],
            "set_reminder": ["remind me", "reminder", "notify me"],
            "insights": ["insight", "analyze", "insights"],
            "unknown": []
        }

    # ----------------- Public ----------------- #
    def detect_intent(
        self,
        user,
        message: str,
        channel: Optional[str] = None,
        previous_context: Optional[Dict[str, Any]] = None,
        top_k_context: int = 3,
    ) -> Dict[str, Any]:
        """
        Main entry: returns standardized dict:
        {
            "intent": str,
            "confidence": float,
            "channel": str,
            "entities": dict,
            "source": "gemini" | "fallback",
            "relevant": { "channel": str, "items": [...] }  # results from retriever
        }
        """
        message = (message or "").strip()
        if not message:
            return {"intent": "unknown", "confidence": 0.0, "channel": channel or "all", "entities": {}, "source": "empty", "relevant": {"items": []}}

        # infer channel heuristically if not provided
        inferred_channel = self._infer_channel_from_text(channel, message, previous_context)

        # fetch relevant context (top_k_context)
        try:
            data = Message.objects.filter(account__user=user)
            relevant_items = retrieve_relevant_messages(user=user, query_text=message, data=data, channel=inferred_channel, top_k=top_k_context) or []
        except Exception as e:
            logger.exception("Retriever failed: %s", e)
            relevant_items = []



        # Call Gemini to get structured intent
        gemini_response = self._call_gemini_for_intent(message, inferred_channel, relevant_items, previous_context)

        parsed = _safe_parse_json(gemini_response)

        if parsed:
            # Normalize and return
            normalized = self._normalize_gemini_output(parsed, inferred_channel)
            normalized["source"] = "gemini"
            normalized["relevant"] = {"channel": inferred_channel, "items": self._format_relevant(relevant_items)}
            # If confidence present and high enough, return
            if normalized.get("confidence", 0) >= 0.55:
                return normalized

        # --- fallback to lightweight rules + NER (if gemini fails or low confidence) ---
        fallback = self._fallback_rules_and_ner(message, inferred_channel, relevant_items)
        fallback["source"] = "fallback"
        fallback["entities"]["input_text"] = message  # ensure query_text is always present
        return fallback



    def _call_gemini_for_intent(self, message: str, channel: str, relevant_items: str, previous_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Build a strict JSON output prompt for Gemini and return the raw text.
        The model is instructed to reply ONLY in JSON.
        """
        system_instructions = """
    You are Whispr, an assistant that converts user requests into a strict JSON structure for routing.
    Before outputting JSON, internally reason step-by-step: 1) Parse the intent. 2) For dates/times, anchor to today's date and calculate relative dates precisely (e.g., "next week Wednesday" means the Wednesday in the following calendar week). 3) Infer trigger dates for reminders separately from event dates.
    Return ONLY valid JSON (no explanation, no backticks). Use keys: intent, confidence, channel, entities.
    Entities is an object and may contain sender, timeframe, query_text, subject, receiver, action, and any other fields you detect.
    If multiple actions are present, list them in entities['actions'] as an array.
    If you cannot determine something, set null or leave key absent.
    """

        prev_ctx = ""
        today_str = datetime.now().strftime("%Y-%m-%d")

        if previous_context:
            prev_ctx = str(previous_context)[:1000]

        # Enhanced prompt with date rules and examples
        prompt = f"""{system_instructions}

    User Message: "{message}"
    Channel (hint): "{channel}"
    Previous Context: "{prev_ctx}"
    For better accuracy of date and time, today is {today_str}. Always calculate relative dates step-by-step using YYYY-MM-DD format:
    - Current week starts on the Monday of {today_str}.
    - "Next week [day]" = the [day] in the week starting next Monday (e.g., if today is Thursday Oct 23 2025, next week starts Mon Oct 27; next Wednesday = Oct 29 2025).
    - "By [time] [date]" sets the reminder trigger (due_datetime) to that exact time/date.
    - Combine due_date + due_time into due_datetime as ISO 8601 (e.g., 2025-10-29T08:00:00; assume 24h format or convert AM/PM).
    - If ambiguous, prioritize the reminder trigger date over the event date.

    Examples (do not include in output; use for reasoning):
    - User: "Remind me about dinner next week Tuesday at 7pm." Today: 2025-10-23. → intent: "set_reminder", due_date: "2025-10-28", due_time: "19:00", due_datetime: "2025-10-28T19:00:00", task_title: "Hey, reminder for your dinner next week Tuesday at 7pm. Enjoy!"
    - User: "Meeting next Friday, remind by 8am next week Wednesday." Today: 2025-10-23. → intent: "set_reminder", due_date: "2025-10-29" (Wednesday trigger), due_time: "08:00", due_datetime: "2025-10-29T08:00:00", task_title: "Hey, I would like to remind you about your meeting next week Friday. Don't forget!"

    Return JSON with this exact schema:
    {{
    "intent": "<one of: find_message, read_message, summarize_message, send_message, reply_message, create_task, set_reminder, insights, unknown>",
    "confidence": 0.0,
    "channel": "<email|whatsapp|slack|calendar|all>",
    "entities": {{
        "iD": - <required> "<the id of the message from Relevant Items (use the data e.g [12, 125])- if the intent is reply or send message or follow up, ensure only specific id is returned but if its a find or summarize or read message, return multiple ids as a list or one>",
        "sender": "<name or org>",
        "receiver_name": "<name of recipient>",
        "receiver": "<email/phone/channel>",
        "subject": "<subject - generate if missing>",
        "body": "<body - generate if missing>",
        "task_type": "<type of task e.g reminder, follow-up, meeting>",
        "task_title": "<natural language report of the finished task as though you are giving a report/reminder to a human about their task e.g hey, i would like to remind you about your meeting with john tomorrow at 3pm, dont forget>",
        "due_time": "<explicit or inferred time e.g. 08:00>",
        "due_date": "<explicit or inferred date e.g. 2025-10-29>",
        "due_datetime": "<ISO 8601 datetime if possible - the due date is the time and date the user wants to be reminded; use best guess for trigger>",
        "query_text": "<user’s query>",
        "actions": ["find", "summarize", "reply", "create_task", "send_message", "insights"],
        "context": "<context or purpose>"
    }}
    }}

    Make sure all applicable fields are filled depending on the detected intent.
    For example:
    - For send_message: include receiver_name, receiver, subject, body
    - For create_task or set_reminder: include task_title, due_date, due_time, due_datetime
    - For find_message or summarize_message: include sender, timeframe, query_text
    """

        try:
            response = self.model.generate_content(prompt)
            text = (response.text or "").strip()
            logger.debug("Gemini raw output: %s", text[:2000])

            # Post-process: Parse JSON and correct dates if needed
            try:
                parsed = json.loads(text)
                if parsed.get('intent') in ['set_reminder', 'create_task']:
                    parsed['entities'] = self._correct_dates(parsed['entities'], today_str, message)
                text = json.dumps(parsed)
            except json.JSONDecodeError:
                logger.warning("Failed to parse Gemini JSON output; returning raw.")
                pass  # Fallback to raw text

            return text
        except Exception as e:
            logger.exception("Gemini generate_content failed: %s", e)
            return ""

    def _correct_dates(self, entities: Dict[str, Any], today_str: str, query_text: str) -> Dict[str, Any]:
        """Post-process entities for accurate date/time calculation."""
        today = datetime.strptime(today_str, "%Y-%m-%d")

        # Helper to calculate "next week [day]" 
        def get_next_week_day(day_name: str) -> datetime:
            day_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
            target_dow = day_map.get(day_name.lower())
            if target_dow is None:
                return today + timedelta(days=7)  # Fallback
            current_dow = today.weekday()
            days_ahead = (target_dow - current_dow + 7) % 7
            if days_ahead == 0:
                days_ahead = 7  # Next week
            return today + timedelta(days=days_ahead)

        # Detect reminder trigger in query (e.g., "remind by 8am next week wednesday")
        query_lower = query_text.lower()
        if 'remind' in query_lower and 'by' in query_lower:
            # Extract day from "next week [day]"
            match = re.search(r'by\s+\d+[ap]m?\s+next\s+week\s+(\w+)', query_lower)
            if match:
                day_name = match.group(1)
                corrected_date = get_next_week_day(day_name)
                entities['due_date'] = corrected_date.strftime("%Y-%m-%d")
                
                # Extract time (simple: assume "8am" or "08:00 AM")
                time_match = re.search(r'by\s+(\d+[:\d]*\s*[ap]m?)', query_lower)
                if time_match:
                    due_time_raw = time_match.group(1).strip()
                    try:
                        # Convert to 24h HH:MM
                        dt_time = datetime.strptime(due_time_raw, "%I%p") if len(due_time_raw) <= 4 else datetime.strptime(due_time_raw, "%I:%M %p")
                        entities['due_time'] = dt_time.strftime("%H:%M")
                        entities['due_datetime'] = f"{entities['due_date']}T{entities['due_time']}:00"
                    except ValueError:
                        entities['due_time'] = due_time_raw  # Keep raw if parse fails
                        entities['due_datetime'] = f"{entities['due_date']}T00:00:00"  # Default midnight
                else:
                    entities['due_datetime'] = f"{entities['due_date']}T08:00:00"  # Assume 8am if not specified
                logger.debug(f"Corrected reminder date to {entities['due_date']}")

        # Fallback: If no trigger detected but relative date in LLM output is suspicious (e.g., wrong weekday), override for common case
        llm_date_str = entities.get('due_date')
        if llm_date_str:
            try:
                llm_date = datetime.strptime(llm_date_str, "%Y-%m-%d")
                # Check if matches expected weekday for "next week wednesday" (hardcode for now; extend as needed)
                if 'wednesday' in query_lower and llm_date.weekday() != 2:
                    corrected = get_next_week_day('wednesday')
                    entities['due_date'] = corrected.strftime("%Y-%m-%d")
                    # Rebuild datetime
                    due_time = entities.get('due_time', '08:00')
                    entities['due_datetime'] = f"{entities['due_date']}T{due_time}:00"
                    logger.debug(f"Overrode invalid Wednesday date from {llm_date_str} to {entities['due_date']}")
            except ValueError:
                pass  # Invalid date, leave as-is

        return entities

    # ----------------- Normalization ----------------- #
    def _normalize_gemini_output(self, parsed: Dict[str, Any], channel_hint: str) -> Dict[str, Any]:
        """
        Ensure returned JSON contains required fields and sensible defaults.
        Also normalize timeframe -> parsed_time where possible.
        """
        intent = parsed.get("intent") or "unknown"
        confidence = parsed.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else 0.0
        except Exception:
            confidence = 0.0

        ch = parsed.get("channel") or channel_hint or "all"
        entities = parsed.get("entities") or {}

        # Normalize timeframe into parsed_time if present
        if entities.get("timeframe") and not entities.get("parsed_time"):
            parsed_time = self._parse_time(entities.get("timeframe"))
            if parsed_time:
                entities["parsed_time"] = parsed_time.strftime("%Y-%m-%d %H:%M:%S")

        # Ensure query_text exists
        if "query_text" not in entities:
            entities["query_text"] = entities.get("query", entities.get("text")) or entities.get("query_text") or None

        return {
            "intent": intent,
            "confidence": confidence,
            "channel": ch,
            "entities": entities,
        }

    # ----------------- Fallback Rules & NER ----------------- #
    def _fallback_rules_and_ner(self, message: str, channel: str, relevant_items: List[Any]) -> Dict[str, Any]:
        """
        Lightweight fallback when Gemini fails: keyword scoring + spaCy NER + date parsing.
        """
        text = message.lower()
        best_intent = "unknown"
        best_score = 0.0

        for intent_name, keywords in self.intent_keywords.items():
            matches = sum(1 for k in keywords if k in text)
            score = matches / max(1, len(keywords))
            if score > best_score:
                best_intent = intent_name
                best_score = score

        # spaCy NER
        entities = {}
        doc = self.nlp(message)
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG") and "sender" not in entities:
                entities["sender"] = ent.text
            if ent.label_ == "DATE" and "timeframe" not in entities:
                entities["timeframe"] = ent.text

        # dateparser best-effort
        parsed = self._parse_time(message)
        if parsed:
            entities["parsed_time"] = parsed.strftime("%Y-%m-%d %H:%M:%S")

        # always keep original message as query_text
        entities["query_text"] = message

        return {
            "intent": best_intent,
            "confidence": round(best_score, 2),
            "channel": channel or "all",
            "entities": entities
        }

    # ----------------- Helpers ----------------- #
    def _infer_channel_from_text(self, channel_hint: Optional[str], message: str, previous_context: Optional[Dict[str, Any]] = None) -> str:
        if channel_hint:
            return channel_hint
        mlower = message.lower()
        if any(k in mlower for k in ("email", "inbox", "subject", "@gmail", "mail")):
            return "email"
        if any(k in mlower for k in ("whatsapp", "wa", "chat", "dm", "message", "text")):
            return "whatsapp"
        if any(k in mlower for k in ("slack", "workspace", "channel")):
            return "slack"
        if previous_context and isinstance(previous_context, dict) and previous_context.get("channel"):
            return previous_context.get("channel")
        return "all"

    def _build_context_text(self, items: List[Any], max_chars: int = 2000) -> str:
        """
        Convert relevant items (ORM objects) into a compact context blob for LLM.
        """
        snippets = []
        for obj in items:
            id = getattr(obj, "id", None)
            snippet = getattr(obj, "snippet", None) or getattr(obj, "content", None) or getattr(obj, "body", None) or ""
            sender = getattr(obj, "sender", "") or getattr(obj, "from_user", "") or ""
            subj = ""
            metadata = getattr(obj, "metadata", {}) or {}
            subj = metadata.get("subject") or ""
            date_field = getattr(obj, "sent_at", None) or getattr(obj, "created_at", None)
            datestr = date_field.strftime("%Y-%m-%d %H:%M") if date_field else ""
            entry = f"From: {sender} | Subject: {subj} | Date: {datestr} | Snippet: {snippet} | ID: {id}"
            snippets.append(entry)
        text = "\n\n".join(snippets)
        if len(text) > max_chars:
            return text[:max_chars]
        return text

    def _format_relevant(self, items: List[Any]) -> List[Dict[str, Any]]:
        formatted = []
        for obj in items:
            snippet = getattr(obj, "snippet", None) or (getattr(obj, "content", "") or "")[:200]
            date_field = getattr(obj, "sent_at", None) or getattr(obj, "created_at", None)
            formatted.append({
                "id": getattr(obj, "id", None),
                "snippet": snippet,
                "date": date_field.strftime("%Y-%m-%d %H:%M") if date_field else None,
                "sender": getattr(obj, "sender", None),
            })
        return formatted

    def _parse_time(self, text: str) -> Optional[datetime]:
        try:
            now = datetime.now()
            parsed = dateparser.parse(text, settings={"RELATIVE_BASE": now})
            return parsed
        except Exception:
            return None
