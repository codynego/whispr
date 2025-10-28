import datetime
import json
from collections import defaultdict
from typing import Dict, List, Union, Any
from threading import Lock  # For thread-safety in multi-threaded access


class ContextManager:
    """
    Manages user conversation context — tracks intents, entities, and message history across channels.
    Supports multiple channels (email, WhatsApp, etc.) per user.
    """

    _instance = None
    _lock = Lock()  # Thread-safety for singleton init

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ContextManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):  # Prevent re-init on subsequent __new__ calls
            # Structure: { user_id: { channel: [ {intent, entities, message, timestamp} ] } }
            self._context_store: Dict[int, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
            self.max_history = 5  # Keep only the last 5 messages per channel
            self._initialized = True

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
        # Access user_id to ensure it's initialized in the defaultdict
        _ = self._context_store[user_id]  # This populates if missing
        # print("Getting context for user:", user_id, "context:", dict(self._context_store[user_id]))  # Convert to plain dict for cleaner print
        user_context = self._ensure_dict(self._context_store[user_id])

        if not user_context:
            return {}

        if channel:
            # Access channel to ensure it's initialized
            _ = user_context[channel]  # Populates the inner defaultdict(list)
            channel_context = self._ensure_dict(user_context[channel])
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
            [ctx.get("message") or "" for ctx in previous_context if isinstance(ctx, dict)]
        )

        return {
            "previous_context": recent_messages.strip(),
            "new_message": new_message.strip(),
        }

    def update_context(self, user_id: int, intent_data: dict) -> None:
        """
        Save or update the user's context for a specific channel.
        Keeps only the last few messages for that channel.
        Thread-safe.
        """
        channel = intent_data.get("channel", "general")
        print("checking intent", intent_data.get("relevant", {}).get("items", []))

        entry = {
            "intent": intent_data.get("intent"),
            "entities": intent_data.get("entities", {}),
            "message": intent_data.get("message"),
            "data": intent_data.get("relevant", {}).get("items", []),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        # Thread-safe append (lock around the whole operation for simplicity)
        with self._lock:
            # Append to user's channel history
            self._context_store[user_id][channel].append(entry)

            # Keep context size limited
            if len(self._context_store[user_id][channel]) > self.max_history:
                self._context_store[user_id][channel] = self._context_store[user_id][channel][-self.max_history:]

        # print(f"Updated context for user {user_id} on channel '{channel}': {entry}")  # Debug print

    def clear_context(self, user_id: int, channel: str = None) -> None:
        """
        Clears the user's context entirely or for a specific channel.
        Thread-safe.
        """
        with self._lock:
            if user_id not in self._context_store:
                return

            if channel:
                self._context_store[user_id].pop(channel, None)
            else:
                self._context_store[user_id] = defaultdict(list)  # Reset to empty for that user