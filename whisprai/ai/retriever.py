from sentence_transformers import SentenceTransformer, util
import numpy as np
from unified.models import Message  # unified message model
from datetime import datetime, timedelta
import re
from typing import List, Optional

# Initialize embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')


def retrieve_relevant_messages(user, data=None, query_text: str = None, channel: str = None, top_k: int = 10):
    """
    Retrieve top-k messages semantically related to a user's query across channels.
    Enhanced with temporal filtering for queries like "any email from yesterday?".
    Works for Email, WhatsApp, Slack, etc., using stored embeddings.
    """
    if not query_text or not query_text.strip():
        return []

    # 1️⃣ Parse temporal constraints from query (e.g., "yesterday", "today", "last week")
    date_filter = _parse_temporal_filter(query_text)


    # 2️⃣ Get user's messages or use provided data
    if data:
        messages = data
    else:
        return []

    # 3️⃣ Apply channel filter if specified
    if channel:
        messages = messages.filter(channel=channel)

    # 4️⃣ Apply temporal filter if detected (assume Message has 'date' field as datetime)
    if date_filter:
        start_date, end_date = date_filter
        messages = messages.filter(sent_at__date__gte=start_date, sent_at__date__lte=end_date)

    if len(messages) == 0:
        return []

    # 5️⃣ Check if query is generic (e.g., "any ... from yesterday?") - if so, sort by recency instead of semantic
    query_lower = query_text.lower().strip().rstrip('?')
    is_generic = len(query_lower.split()) < 4 or query_lower.startswith('any ') or 'from yesterday' in query_lower

    if is_generic and date_filter:
        # For generic temporal queries, return top_k most recent
        relevant_messages = list(messages.order_by('-sent_at')[:top_k])
    else:
        # 6️⃣ Generate embedding for the query (only for non-generic)
        query_embedding = model.encode([query_text], normalize_embeddings=True)

        # 7️⃣ Compute cosine similarity between query and each message
        scored_messages = []
        for msg in messages:
            try:
                msg_vec = np.array(msg.embedding, dtype=np.float32)
                similarity = util.cos_sim(query_embedding, msg_vec)[0][0].item()
                scored_messages.append((similarity, msg))
            except Exception as e:
                print(f"[Retriever Error for Message {msg.id}]: {e}")
                continue

        # 8️⃣ Sort by highest similarity
        scored_messages.sort(key=lambda x: x[0], reverse=True)
        relevant_messages = [msg for _, msg in scored_messages[:top_k]]

    return relevant_messages


def _parse_temporal_filter(query_text: str) -> Optional[tuple]:
    """
    Simple parser for common temporal phrases in query_text.
    Returns (start_date, end_date) as datetime objects, or None if no temporal detected.
    """
    query_lower = query_text.lower()
    today = datetime.now()
    end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)  # End of today

    if 'yesterday' in query_lower:
        start_date = (today - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_date, end_date
    elif 'today' in query_lower:
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_date, end_date
    elif 'last week' in query_lower:
        # Approximate: last 7 days
        start_date = today - timedelta(days=7)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_date, end_date
    elif 'this week' in query_lower:
        # Monday to today
        days_to_monday = today.weekday()  # 0=Monday
        start_date = today - timedelta(days=days_to_monday)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_date, end_date

    # Extend with regex for more patterns, e.g., "from Oct 22"
    date_match = re.search(r'from (\w+ \d+)', query_text, re.IGNORECASE)
    if date_match:
        try:
            # Use dateutil.parser for flexibility (install if needed: pip install python-dateutil)
            from dateutil import parser
            parsed_date = parser.parse(date_match.group(1), fuzzy=True)
            start_date = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = parsed_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_date, end_date
        except ImportError:
            print("Install python-dateutil for better date parsing.")
        except ValueError:
            pass

    return None