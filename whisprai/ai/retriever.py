# # retriever.py
# from sentence_transformers import SentenceTransformer, util
# import numpy as np
# from emails.models import Email

# # Initialize the same model used for email importance
# model = SentenceTransformer('all-MiniLM-L6-v2')


# def retrieve_relevant_emails(user, data=None, query_text: str = None, top_k: int = 5):
#     """
#     Retrieve top-k emails semantically related to a user's query using embeddings.
#     Automatically generates embeddings for the query and compares with stored email vectors.
#     """
#     if not query_text or not query_text.strip():
#         return []

#     # 1️⃣ Generate embedding for the query
#     query_embedding = model.encode([query_text], normalize_embeddings=True)

#     # 2️⃣ Fetch user emails that have stored embeddings
#     if data:
#         emails = data
#     else:
#         emails = Email.objects.filter(account__user=user, embedding__isnull=False)
#     if not emails.exists():
#         return []

#     # 3️⃣ Compute cosine similarity between query and each email
#     scored_emails = []
#     for email in emails:
#         try:
#             email_vec = np.array(email.embedding, dtype=np.float32)
#             similarity = util.cos_sim(query_embedding, email_vec)[0][0].item()
#             scored_emails.append((similarity, email))
#         except Exception as e:
#             print(f"[Retriever Error for Email {email.id}]: {e}")
#             continue

#     # 4️⃣ Sort by highest similarity and return top_k
#     scored_emails.sort(key=lambda x: x[0], reverse=True)
#     relevant_emails = [email for _, email in scored_emails[:top_k]]

#     return relevant_emails




# retriever.py
from sentence_transformers import SentenceTransformer, util
import numpy as np
from unified.models import Message  # unified message model


# Initialize embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')


def retrieve_relevant_messages(user, data=None, query_text: str = None, channel: str = None, top_k: int = 5):
    """
    Retrieve top-k messages semantically related to a user's query across channels.
    Works for Email, WhatsApp, Slack, etc., using stored embeddings.
    """
    print("data in retriever:", data)
    if not query_text or not query_text.strip():
        return []

    # 1️⃣ Generate embedding for the query
    query_embedding = model.encode([query_text], normalize_embeddings=True)

    # 2️⃣ Get user's messages or use provided data
    if data:
        messages = data
    else:
        messages = Message.objects.filter(user=user, embedding__isnull=False)

    if channel:
        messages = messages.filter(channel=channel)

    if not messages.exists():
        return []

    # 3️⃣ Compute cosine similarity between query and each message
    scored_messages = []
    for msg in messages:
        try:
            msg_vec = np.array(msg.embedding, dtype=np.float32)
            similarity = util.cos_sim(query_embedding, msg_vec)[0][0].item()
            scored_messages.append((similarity, msg))
        except Exception as e:
            print(f"[Retriever Error for Message {msg.id}]: {e}")
            continue

    # 4️⃣ Sort by highest similarity
    scored_messages.sort(key=lambda x: x[0], reverse=True)
    relevant_messages = [msg for _, msg in scored_messages[:top_k]]
    print("relevant_messages in retriever:", relevant_messages)

    return relevant_messages
