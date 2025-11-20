from openai import OpenAI
client = OpenAI()

def generate_embedding(text: str):
    text = text.strip()
    if not text:
        return None
    
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding
