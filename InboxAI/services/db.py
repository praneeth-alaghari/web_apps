import os
import datetime
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
COLLECTION_NAME = "inbox_training"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def init_db():
    try:
        collections = client.get_collections().collections
        names = [c.name for c in collections]
        if COLLECTION_NAME not in names:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
            print(f"Created Qdrant collection: {COLLECTION_NAME}")
    except Exception as e:
        print(f"Qdrant init error: {e}")

def get_embedding(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding

def store_training_action(email_id: str, action: str, sender: str, subject: str, snippet: str):
    content = f"Subject: {subject}\nSnippet: {snippet}"
    vector = get_embedding(content)
    
    payload = {
        "action": action,
        "sender": sender,
        "subject": subject,
        "timestamp": datetime.datetime.now().isoformat(),
        "source": "training"
    }

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=hash(email_id) % (2**63 - 1),
                vector=vector,
                payload=payload
            )
        ]
    )


def get_preference_decision(subject: str, snippet: str):
    """
    Search Qdrant for Top K similar emails to decide action.
    Returns: { "action": str, "confidence": float, "source": "MEM" }
    """
    content = f"Subject: {subject}\nSnippet: {snippet}"
    vector = get_embedding(content)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=5
    ).points

    if not results:
        return {"action": "UNCERTAIN", "confidence": 0.0, "source": "NONE"}

    keep_count = sum(1 for r in results if r.payload.get("action") == "KEEP")
    delete_count = sum(1 for r in results if r.payload.get("action") == "DELETE")

    total = len(results)
    keep_score = keep_count / total
    delete_score = delete_count / total

    if keep_score >= 0.7:
        return {"action": "KEEP", "confidence": keep_score, "source": "MEM"}
    elif delete_score >= 0.7:
        return {"action": "DELETE", "confidence": delete_score, "source": "MEM"}
    else:
        return {
            "action": "UNCERTAIN",
            "confidence": max(keep_score, delete_score),
            "source": "MEM"
        }


init_db()

