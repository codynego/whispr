# # whispr/ai_core/context_manager.py
# import datetime

# class ContextManager:
#     """
#     Handles conversation context — retrieves, merges, and updates the user's last intent and entities.
#     """

#     def __init__(self):
#         # For now, use a simple in-memory store (you can swap this for Redis or DB later)
#         self._context_store = {}

#     def get_context(self, user_id: int):
#         """
#         Get the last known context for a user.
#         """
#         return self._context_store.get(user_id, {})

#     def merge(self, previous_context: dict, new_message: str):
#         """
#         Merge previous context with the current message.
#         If the new message looks like a follow-up, combine them for intent detection.
#         """
#         if not previous_context:
#             # No prior context
#             return new_message

#         # Simple logic — you can make this smarter later
#         last_intent = previous_context.get("intent")
#         last_entities = previous_context.get("entities", {})
#         merged = {
#             "previous_intent": last_intent,
#             "previous_entities": last_entities,
#             "new_message": new_message,
#         }
#         return merged

#     def update_context(self, user_id: int, intent_data: dict):
#         """
#         Save or update the user's context after each processed message.
#         """
#         context_entry = {
#             "intent": intent_data.get("intent"),
#             "entities": intent_data.get("entities", {}),
#             "timestamp": datetime.datetime.utcnow().isoformat()
#         }
#         self._context_store[user_id] = context_entry

#     def clear_context(self, user_id: int):
#         """
#         Clears the user's conversation context (for example, after long inactivity).
#         """
#         if user_id in self._context_store:
#             del self._context_store[user_id]



import datetime
import json
from collections import defaultdict
from typing import Dict, List, Union, Any


class ContextManager:
    """
    Manages user conversation context — tracks intents, entities, and message history across channels.
    Supports multiple channels (email, WhatsApp, etc.) per user.
    """

    def __init__(self):
        # Structure: { user_id: { channel: [ {intent, entities, message, timestamp} ] } }
        self._context_store: Dict[int, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        self.max_history = 5  # Keep only the last 5 messages per channel

    # ----------------------------
    # Utility methods
    # ----------------------------

    def _ensure_dict(self, data: Union[str, dict, list, None]) -> Union[dict, list]:
        """Ensure data is parsed from JSON string if needed."""
        if isinstance(data, str):
            try:
                parsed = json.loads(data)
                return parsed if isinstance(parsed, (dict, list)) else {}
            except json.JSONDecodeError:
                return {}
        return data or {}

    # ----------------------------
    # Core methods
    # ----------------------------

    def get_context(self, user_id: int, channel: str = None) -> Union[dict, list]:
        """
        Retrieve the recent conversation context for a user.
        - If `channel` is specified: return the last few entries from that channel.
        - Otherwise: merge and return the latest context from all channels.
        """
        user_context = self._ensure_dict(self._context_store.get(user_id, {}))

        if not user_context:
            return {}

        if channel:
            channel_context = self._ensure_dict(user_context.get(channel, []))
            return channel_context[-self.max_history:] if isinstance(channel_context, list) else []

        # Merge across all channels
        merged: List[Dict[str, Any]] = []
        for ch, records in user_context.items():
            if isinstance(records, list):
                merged.extend(records[-self.max_history:])

        merged.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return merged[:self.max_history]

    def merge(self, previous_context: Union[list, dict, str, None], new_message: str) -> dict:
        """
        Merge previous context into a new structured message context for intent detection.
        """
        previous_context = self._ensure_dict(previous_context)

        if not previous_context:
            return {"new_message": new_message}

        if isinstance(previous_context, dict):
            previous_context = [previous_context]

        recent_messages = " ".join(
            [ctx.get("message", "") for ctx in previous_context if isinstance(ctx, dict)]
        )

        return {
            "previous_context": recent_messages.strip(),
            "new_message": new_message.strip(),
        }

    def update_context(self, user_id: int, intent_data: dict) -> None:
        """
        Save or update the user's context for a specific channel.
        Keeps only the last few messages for that channel.
        """
        channel = intent_data.get("channel", "general")

        entry = {
            "intent": intent_data.get("intent"),
            "entities": intent_data.get("entities", {}),
            "message": intent_data.get("message"),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        # Append to user's channel history
        self._context_store[user_id][channel].append(entry)

        # Keep context size limited
        if len(self._context_store[user_id][channel]) > self.max_history:
            self._context_store[user_id][channel] = self._context_store[user_id][channel][-self.max_history:]

    def clear_context(self, user_id: int, channel: str = None) -> None:
        """
        Clears the user's context entirely or for a specific channel.
        """
        if user_id not in self._context_store:
            return

        if channel:
            self._context_store[user_id].pop(channel, None)
        else:
            self._context_store.pop(user_id, None)
