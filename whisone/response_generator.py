class ResponseGenerator:
    """
    Generates responses based on the structured user message:
    - intent
    - entities
    - memory relevance
    - conversation context
    """

    def __init__(self, memory_store, llm):
        self.memory_store = memory_store   # e.g., KnowledgeVault instance
        self.llm = llm                     # wrapper for OpenAI calls

    def generate(self, structured):
        """
        structured = {
            "intent": str,
            "entities": {...},
            "should_write_memory": bool,
            "should_query_memory": bool,
            "memory_matches": [...],
            "user_message": str
        }
        """
        intent = structured["intent"]
        entities = structured.get("entities", {})
        memory_matches = structured.get("memory_matches", [])
        user_message = structured["user_message"]

        # 1. If question AND memory exists → answer using memory
        if intent == "ask_question" and memory_matches:
            return self._answer_with_memory(user_message, memory_matches)

        # 2. If journaling → generate reflective response
        if intent == "journal_entry":
            return self._journal_response(user_message)

        # 3. If casual chat → casual response
        if intent == "casual":
            return self._casual_response(user_message)

        # 4. If shopping related
        if intent == "shopping_note":
            return self._shopping_response(user_message, entities, memory_matches)

        # 5. Default fallback
        return self._generic_response(user_message)

    # --------------------------------------------------------------------
    # HANDLERS
    # --------------------------------------------------------------------

    def _answer_with_memory(self, question, memory_matches):
        """Use memory to answer a user’s question."""
        context_text = "\n".join([m["content"] for m in memory_matches])

        prompt = f"""
You are Whisone.
The user asked a question:

Question:
{question}

Relevant memory:
{context_text}

Answer using ONLY the relevant memory, keep it simple and helpful.
"""
        return self.llm.chat(prompt)

    def _journal_response(self, text):
        """Respond to journaling entries with reflective, supportive tone."""
        prompt = f"""
User wrote a journal entry:

\"\"\"{text}\"\"\"

Your job:
- Acknowledge their reflections
- Highlight key themes
- Offer optional insights
- Do NOT give advice unless it's natural
- Keep tone warm, neutral, and human-like

Write 3–5 sentences.
"""
        return self.llm.chat(prompt)

    def _casual_response(self, text):
        prompt = f"""
User said: {text}

Respond casually, friendly, without overthinking.
"""
        return self.llm.chat(prompt)

    def _shopping_response(self, msg, entities, matches):
        items = entities.get("items", [])
        stores = entities.get("stores", [])

        previous_notes = "\n".join([m["content"] for m in matches]) if matches else "None"

        prompt = f"""
The user left a shopping-related message:

Message:
{msg}

Extracted items: {items}
Stores: {stores}

Previous related memory:
{previous_notes}

Respond by:
- Acknowledging the shopping list or observation
- Mentioning if memory contains past related items
- Keeping it simple and practical
"""
        return self.llm.chat(prompt)

    def _generic_response(self, text):
        prompt = f"""
User said: {text}

Respond helpfully and naturally.
"""
        return self.llm.chat(prompt)
