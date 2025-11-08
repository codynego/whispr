
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

# from whisprai.ai.retriever import retrieve_relevant_messages  # your existing retriever
    # ----------------- Gemini calling ----------------- #
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# ----------------- Embedding Helper (kept for retrieval purposes) ----------------- #
# _embedding_model = None
# def get_embedding_model():
#     global _embedding_model
#     if _embedding_model is None:
#         _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
#     return _embedding_model

# def generate_embedding(text: str):
#     if not text or not text.strip():
#         return []
#     model = get_embedding_model()
#     emb = model.encode([text], normalize_embeddings=True)
#     return emb[0].tolist()

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
        # try:
        #     data = Message.objects.filter(account__user=user)
        #     relevant_items = retrieve_relevant_messages(user=user, query_text=message, data=data, channel=inferred_channel, top_k=top_k_context) or []
        # except Exception as e:
        #     logger.exception("Retriever failed: %s", e)
        #     relevant_items = []
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



    def _call_gemini_for_intent(
        self,
        message: str,
        channel: str,
        relevant_items: List[Dict[str, Any]] = None,  # Fixed: Typed as List[Dict]; unused but future-proof
        previous_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Convert a user message into a strict JSON structure for routing,
        supporting reminders, tasks, messages, and full automation workflows.
        Returns JSON as string.
        """
        system_instructions = """
    You are Whispr, an assistant that converts user requests into strict JSON for tasks and automations.
    Before outputting JSON, reason step-by-step: 1) Parse the intent. 2) Resolve relative dates/times. 3) Identify ALL multi-step automation actions mentioned and chain them logically in order (e.g., fetch data → process/summarize → send/output). ALWAYS include every action described in the user message—do not omit any, even if 3+ steps.
    Return ONLY valid JSON (no explanation, no backticks) with keys: intent, confidence, channel, entities.

    Entities may contain:
    - message_id, sender, receiver_name, receiver, subject, body
    - action_type, name, next_run_at, description, query_text, actions, context
    - trigger_type, recurrence_pattern, trigger_condition, action_params, execution_mode
    - __should_create_automation__, workflow

    For automations, the workflow JSON must include:
    - trigger.type: one of "on_schedule", "on_email_received", "on_message_received", "manual"
    - trigger.config: schedule time, email label, day_of_week, or other necessary info
    - actions: ALWAYS a list of ALL actions from the query, even if 3+ steps. types: one of ["extract_fields", "append_google_sheet", "send_whatsapp_message", "create_calendar_event", "send_email", "fetch_calendar_events", "append_notion_page", "fetch_unread_emails", "fetch_last_week_reports", "summarize_messages"]
    - actions.config: required fields per action:
        - extract_fields → "fields": ["field1","field2"]
        - append_google_sheet → "spreadsheet_name", "columns"
        - send_whatsapp_message → "receiver_name", "message_template"
        - create_calendar_event → "event_title", "time", "duration", "calendar_id"
        - send_email → "receiver", "subject", "body"
        - fetch_calendar_events → "calendar_id", "date"
        - append_notion_page → "database_name", "fields_mapping"
        - fetch_unread_emails → "label": "inbox|all", "filter": "unread|starred", "limit": 50
        - fetch_last_week_reports → "timeframe": "last_week", "source": "emails|docs"
        - summarize_messages → "input": "{fetched_data}", "style": "concise|detailed"

    If a field cannot be determined, infer reasonably or set null. Use placeholders like {fetched_data} for chaining outputs.
    Use examples to illustrate multi-action chaining:
    - "Remind me about dinner next Tuesday at 7pm." → intent: "automation_create", next_run_at: "2025-11-11T19:00:00", action_type: "reminder"
    - "Every morning at 8 AM, send my calendar events to WhatsApp." → intent: "automation_create",
    workflow: {
        "trigger": {"type":"on_schedule", "config":{"time":"08:00","timezone":"Africa/Lagos"}},
        "actions":[
            {"type":"fetch_calendar_events","config":{"calendar_id":"primary"}},
            {"type":"send_whatsapp_message","config":{"message_template":"Good morning! {event_list}"}}
        ]
    }
    - "Every day at 9 AM, summarize unread emails and save to Notion." → intent: "automation_create",
    workflow: {
        "trigger": {"type":"on_schedule", "config":{"time":"09:00","timezone":"Africa/Lagos"}},
        "actions":[
            {"type":"fetch_unread_emails","config":{"label":"inbox","filter":"unread","limit":50}},
            {"type":"summarize_messages","config":{"input":"{fetched_emails}","style":"concise"}},
            {"type":"append_notion_page","config":{"database_name":"Daily Log","fields_mapping":{"Title":"{current_date} Summary","Content":"{summary}"}}}
        ]
    },
    recurrence_pattern: "daily"
    - "Every Monday, send WhatsApp to Sarah, create calendar event, email report summary." → intent: "automation_create",
    workflow: {
        "trigger": {"type":"on_schedule", "config":{"day_of_week":"Monday","time":"11:00","timezone":"Africa/Lagos"}},
        "actions":[
            {"type":"send_whatsapp_message","config":{"receiver_name":"Sarah","message_template":"Reminder: Weekly meeting!"}},
            {"type":"create_calendar_event","config":{"event_title":"Team Sync","time":"11:00","duration":60,"calendar_id":"primary"}},
            {"type":"fetch_last_week_reports","config":{"timeframe":"last_week","source":"reports"}},
            {"type":"summarize_messages","config":{"input":"{fetched_reports}","style":"concise"}},
            {"type":"send_email","config":{"receiver":"manager@company.com","subject":"Weekly Report Summary","body":"{report_summary}"}}
        ]
    },
    recurrence_pattern: "weekly on Monday"
    """

        prev_ctx = ""
        today_str = datetime.now().strftime("%Y-%m-%d")  # Dynamic; was hardcoded for testing
        if previous_context:
            prev_ctx = str(previous_context)[:1000]

        prompt = f"""{system_instructions}

    User Message: "{message}"
    Channel (hint): "{channel}"
    Previous Context: "{prev_ctx}"
    Today is {today_str}. Convert relative dates (e.g., 'next Monday') to ISO 8601 (UTC).
    Return JSON strictly following this schema:
    {{
    "intent": "<one of: find_message, read_message, summarize_message, send_message, reply_message, automation_create, automation_update, automation_delete, insights, unknown>",
    "confidence": 0.0,
    "channel": "<email|whatsapp|slack|calendar|all>",
    "entities": {{
        "message_id": [12,125],
        "sender": "<name or org>",
        "receiver_name": "<name of recipient>",
        "receiver": "<email/phone/channel>",
        "subject": "<subject - generate if missing>",
        "body": "<body - generate if missing>",
        "action_type": "<type of action e.g. reminder, follow-up, summary, auto_followup>",
        "name": "<natural language name — e.g. 'Remind Abednego to reply to John tomorrow at 9am'>",
        "next_run_at": "<ISO 8601 datetime — inferred if missing>",
        "description": "<optional description for the automation>",
        "query_text": "<the user's raw query>",
        "actions": ["find","summarize","reply","create_task","send_message","insights"],
        "context": "<context or purpose of request>",
        "trigger_type": "<on_email_received|on_schedule|on_message_received|on_task_due|on_calendar_event|manual>",
        "recurrence_pattern": "<daily|weekly|every Monday|cron string>",
        "trigger_condition": {{"channel":"<email|whatsapp|all>", "filter":"<optional filter>"}},
        "action_params": {{"actions":["find","summarize","reply","create_task","send_message","insights"], "config":{{}}}},
        "execution_mode": "<manual|auto|background>",
        "__should_create_automation__": false,
        "workflow": {{
            "trigger": {{"type":"TRIGGER_TYPE","config":{{}}}},
            "actions": [{{"type":"ACTION_TYPE","config":{{}}}}]  // ALWAYS full list of actions
        }}
    }}
    }}"""

        try:
            response = self.model.generate_content(prompt)
            raw_text = (response.text or "").strip()

            # Parse JSON
            try:
                parsed = json.loads(raw_text)

                # Correct dates / next_run_at for reminders or automation schedules
                if parsed.get("intent") in ["automation_create", "automation_update"]:
                    parsed["entities"] = self._correct_dates(
                        parsed.get("entities", {}), today_str, message
                    )

                # Boost confidence for complete multi-actions
                if "workflow" in parsed.get("entities", {}) and len(parsed["entities"]["workflow"].get("actions", [])) > 1:
                    parsed["confidence"] = max(parsed.get("confidence", 0.0), 0.8)

                # Ensure actions array exists
                if "actions" not in parsed.get("entities", {}):
                    parsed["entities"]["actions"] = []

                # Ensure action_params exists
                if "action_params" not in parsed.get("entities", {}):
                    parsed["entities"]["action_params"] = {
                        "actions": parsed["entities"]["actions"],
                        "config": {}
                    }

                # Ensure workflow exists and has actions list
                if "workflow" not in parsed.get("entities", {}):
                    parsed["entities"]["workflow"] = {
                        "trigger": {"type": None, "config": {}},
                        "actions": []
                    }
                else:
                    parsed["entities"]["workflow"].setdefault("actions", [])

                # Set automation flag
                if parsed.get("intent", "").startswith("automation"):
                    parsed["entities"]["__should_create_automation__"] = True

                # Fill missing keys with null
                defaults = ["message_id","sender","receiver_name","receiver","subject","body",
                            "action_type","name","next_run_at","description","query_text",
                            "context","trigger_type","recurrence_pattern","trigger_condition","execution_mode"]
                for key in defaults:
                    parsed["entities"].setdefault(key, None)

                return json.dumps(parsed)

            except json.JSONDecodeError:
                logger.warning("Failed to parse Gemini JSON; returning raw.")
                return raw_text

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
