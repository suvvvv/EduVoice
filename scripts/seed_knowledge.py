"""Seed the Qdrant collection with educational knowledge base."""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant_client.models import Distance, VectorParams, PointStruct

from app.config import COLLECTION_NAME, EMBEDDING_DIM
from app.rag import get_qdrant_client, get_embedding


def seed():
    # Load knowledge data
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge.json")
    with open(data_path) as f:
        knowledge = json.load(f)

    print(f"Loaded {len(knowledge)} knowledge chunks")

    # Recreate collection
    collections = [c.name for c in get_qdrant_client().get_collections().collections]
    if COLLECTION_NAME in collections:
        get_qdrant_client().delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection: {COLLECTION_NAME}")

    get_qdrant_client().create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    print(f"Created collection: {COLLECTION_NAME}")

    # Generate embeddings and upsert
    points = []
    for i, item in enumerate(knowledge):
        print(f"  Embedding [{i+1}/{len(knowledge)}]: {item['subject']} - {item['topic']}")
        embedding = get_embedding(item["text"])
        points.append(
            PointStruct(
                id=i,
                vector=embedding,
                payload={
                    "text": item["text"],
                    "subject": item["subject"],
                    "topic": item["topic"],
                },
            )
        )

    get_qdrant_client().upsert(collection_name=COLLECTION_NAME, points=points)
    print(f"\nSuccessfully seeded {len(points)} documents into '{COLLECTION_NAME}'")


if __name__ == "__main__":
    seed()
