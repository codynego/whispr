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
from collections import defaultdict

class ContextManager:
    """
    Handles conversation context — retrieves, merges, and updates the user's last intent,
    entities, and message history across channels.
    """

    def __init__(self):
        # Store structured as: { user_id: { channel: [ {intent, entities, message, timestamp} ] } }
        self._context_store = defaultdict(lambda: defaultdict(list))
        self.max_history = 5  # Keep only last 5 context items per channel

    def get_context(self, user_id: int, channel: str = None):
        """
        Retrieve recent context for a user.
        If channel is provided → return last few entries from that channel.
        If not provided → return merged context from all channels.
        """
        user_context = self._context_store.get(user_id, {})

        if not user_context:
            return {}

        if channel:
            # Get most recent few entries from that channel
            return user_context.get(channel, [])[-self.max_history:]

        # Merge across all channels (useful when no channel is specified)
        merged = []
        for ch, records in user_context.items():
            merged.extend(records[-self.max_history:])
        merged.sort(key=lambda x: x.get("timestamp"), reverse=True)

        return merged[:self.max_history]

    def merge(self, previous_context: list, new_message: str):
        """
        Combine previous context messages with the new one for better intent detection.
        """
        if not previous_context:
            return new_message

        # Join previous message texts for context
        recent_messages = " ".join(
            [ctx.get("message", "") for ctx in previous_context if "message" in ctx]
        )

        merged = {
            "previous_context": recent_messages,
            "new_message": new_message,
        }
        return merged

    def update_context(self, user_id: int, channel: str, intent_data: dict):
        """
        Save or update the user's context for a specific channel after each processed message.
        """
        entry = {
            "intent": intent_data.get("intent"),
            "entities": intent_data.get("entities", {}),
            "message": intent_data.get("message"),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        # Append to channel-specific list
        self._context_store[user_id][channel].append(entry)

        # Keep context size limited
        if len(self._context_store[user_id][channel]) > self.max_history:
            self._context_store[user_id][channel] = self._context_store[user_id][channel][-self.max_history:]

    def clear_context(self, user_id: int, channel: str = None):
        """
        Clears user's context — optionally for a single channel or for all.
        """
        if user_id not in self._context_store:
            return

        if channel:
            if channel in self._context_store[user_id]:
                del self._context_store[user_id][channel]
        else:
            del self._context_store[user_id]
