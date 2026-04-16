"""RAG pipeline: embed query -> search Qdrant -> generate answer with LLM."""

from openai import OpenAI
from qdrant_client import QdrantClient

from app.config import (
    OPENAI_API_KEY,
    QDRANT_URL,
    QDRANT_API_KEY,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    LLM_MODEL,
)

_openai_client = None
_qdrant_client = None


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        if QDRANT_URL and QDRANT_API_KEY:
            _qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        else:
            _qdrant_client = QdrantClient(":memory:")
    return _qdrant_client


SYSTEM_PROMPT = """You are EduVoice, a friendly and patient voice-based learning assistant for students.

Rules:
- Give clear, concise explanations suitable for spoken conversation (the student is LISTENING, not reading).
- Keep answers under 3-4 sentences unless the student asks for detail.
- Use simple language. Avoid jargon unless explaining it.
- If context documents are provided, base your answer on them. If they don't cover the question, say so honestly and give your best general knowledge answer.
- When explaining math or formulas, describe them in words (e.g., "a squared plus b squared equals c squared").
- Be encouraging. If a student is confused, reassure them and try a different angle.
- Support multilingual queries — if the student speaks in Hindi or another language, respond in the same language.
- At the end of your answer, ask a brief follow-up like "Does that make sense?" or "Want me to explain further?"
"""


def get_embedding(text: str) -> list[float]:
    """Get embedding vector for a text string."""
    response = get_openai_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def search_knowledge(query: str, top_k: int = 3) -> list[dict]:
    """Search Qdrant for relevant knowledge chunks."""
    query_vector = get_embedding(query)

    try:
        results = get_qdrant_client().query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "text": point.payload.get("text", ""),
                "subject": point.payload.get("subject", ""),
                "topic": point.payload.get("topic", ""),
                "score": point.score,
            }
            for point in results.points
        ]
    except Exception as e:
        print(f"Qdrant search error: {e}")
        return []


def generate_answer(query: str, conversation_history: list[dict] | None = None) -> str:
    """RAG: retrieve context from Qdrant, then generate answer with LLM."""
    # Step 1: Retrieve relevant documents
    context_docs = search_knowledge(query)

    # Step 2: Build context string
    if context_docs:
        context_str = "\n\n".join(
            f"[{doc['subject']} - {doc['topic']}]\n{doc['text']}"
            for doc in context_docs
            if doc["score"] > 0.3
        )
    else:
        context_str = ""

    # Step 3: Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context_str:
        messages.append(
            {
                "role": "system",
                "content": f"Relevant knowledge base context:\n\n{context_str}",
            }
        )

    # Add conversation history for multi-turn context
    if conversation_history:
        messages.extend(conversation_history[-6:])  # Last 3 exchanges

    messages.append({"role": "user", "content": query})

    # Step 4: Generate
    response = get_openai_client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=300,
        temperature=0.7,
    )

    return response.choices[0].message.content
