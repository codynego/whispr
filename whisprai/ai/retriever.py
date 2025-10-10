# retriever.py
from sentence_transformers import SentenceTransformer, util
import numpy as np
from emails.models import Email

# Initialize the same model used for email importance
model = SentenceTransformer('all-MiniLM-L6-v2')


def retrieve_relevant_emails(user, query_text: str, top_k: int = 5):
    """
    Retrieve top-k emails semantically related to a user's query using embeddings.
    Automatically generates embeddings for the query and compares with stored email vectors.
    """
    if not query_text or not query_text.strip():
        return []

    # 1️⃣ Generate embedding for the query
    query_embedding = model.encode([query_text], normalize_embeddings=True)

    # 2️⃣ Fetch user emails that have stored embeddings
    emails = Email.objects.filter(account__user=user).exclude(embedding=None)
    if not emails.exists():
        return []

    # 3️⃣ Compute cosine similarity between query and each email
    scored_emails = []
    for email in emails:
        try:
            email_vec = np.array(email.embedding, dtype=np.float32)
            similarity = util.cos_sim(query_embedding, email_vec)[0][0].item()
            scored_emails.append((similarity, email))
        except Exception as e:
            print(f"[Retriever Error for Email {email.id}]: {e}")
            continue

    # 4️⃣ Sort by highest similarity and return top_k
    scored_emails.sort(key=lambda x: x[0], reverse=True)
    relevant_emails = [email for _, email in scored_emails[:top_k]]

    return relevant_emails
