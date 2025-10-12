# whispr/ai_core/context_manager.py
import datetime

class ContextManager:
    """
    Handles conversation context — retrieves, merges, and updates the user's last intent and entities.
    """

    def __init__(self):
        # For now, use a simple in-memory store (you can swap this for Redis or DB later)
        self._context_store = {}

    def get_context(self, user_id: int):
        """
        Get the last known context for a user.
        """
        return self._context_store.get(user_id, {})

    def merge(self, previous_context: dict, new_message: str):
        """
        Merge previous context with the current message.
        If the new message looks like a follow-up, combine them for intent detection.
        """
        if not previous_context:
            # No prior context
            return new_message

        # Simple logic — you can make this smarter later
        last_intent = previous_context.get("intent")
        last_entities = previous_context.get("entities", {})
        merged = {
            "previous_intent": last_intent,
            "previous_entities": last_entities,
            "new_message": new_message,
        }
        return merged

    def update_context(self, user_id: int, intent_data: dict):
        """
        Save or update the user's context after each processed message.
        """
        context_entry = {
            "intent": intent_data.get("intent"),
            "entities": intent_data.get("entities", {}),
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        self._context_store[user_id] = context_entry

    def clear_context(self, user_id: int):
        """
        Clears the user's conversation context (for example, after long inactivity).
        """
        if user_id in self._context_store:
            del self._context_store[user_id]
