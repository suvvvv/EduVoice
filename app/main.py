"""EduVoice — Voice-First Learning Assistant.

FastAPI server that handles Vapi webhook events for a voice-based
educational RAG agent powered by Qdrant + OpenAI.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import HOST, PORT
from app.rag import generate_answer

app = FastAPI(title="EduVoice", version="1.0.0")

# In-memory conversation store (keyed by call ID)
conversations: dict[str, list[dict]] = {}


@app.get("/")
async def health():
    return {"status": "ok", "service": "EduVoice"}


@app.post("/vapi/webhook")
async def vapi_webhook(request: Request):
    """Handle all Vapi server messages.

    Vapi sends a POST with a JSON body containing a `message` field.
    We handle the relevant message types:
    - assistant-request: return assistant config
    - function-call: handle tool calls
    - conversation-update: track conversation history
    - end-of-call-report: cleanup
    """
    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type", "")

    if msg_type == "assistant-request":
        return _handle_assistant_request()

    if msg_type == "function-call":
        return await _handle_function_call(message)

    if msg_type == "conversation-update":
        _handle_conversation_update(message)
        return JSONResponse(content={"status": "ok"})

    if msg_type == "end-of-call-report":
        call_id = message.get("call", {}).get("id", "")
        conversations.pop(call_id, None)
        return JSONResponse(content={"status": "ok"})

    return JSONResponse(content={"status": "ok"})


def _handle_assistant_request():
    """Return assistant configuration when Vapi asks for it."""
    return JSONResponse(
        content={
            "assistant": {
                "model": {
                    "provider": "custom-llm",
                    "url": "",  # Will be set to our /vapi/chat endpoint
                    "model": "eduvoice-rag",
                },
                "voice": {
                    "provider": "11labs",
                    "voiceId": "21m00Tcm4TlvDq8ikWAM",  # Rachel - clear, friendly
                },
                "firstMessage": "Hi! I'm EduVoice, your learning assistant. You can ask me anything about science, math, history, or any subject. What would you like to learn today?",
                "transcriber": {
                    "provider": "deepgram",
                    "model": "nova-2",
                    "language": "multi",  # Multilingual support
                },
            }
        }
    )


@app.post("/vapi/chat")
async def vapi_chat(request: Request):
    """Custom LLM endpoint for Vapi.

    Vapi sends OpenAI-compatible chat completion requests here.
    We intercept the user message, run RAG, and return the response.
    """
    body = await request.json()
    messages = body.get("messages", [])
    call_id = body.get("call", {}).get("id", "unknown")

    # Extract the latest user message
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        return _chat_response("I didn't catch that. Could you repeat your question?")

    # Get conversation history for this call
    history = conversations.get(call_id, [])

    # Generate RAG answer
    answer = generate_answer(user_message, conversation_history=history)

    # Update conversation history
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": answer})
    conversations[call_id] = history

    return _chat_response(answer)


async def _handle_function_call(message: dict):
    """Handle function/tool calls from Vapi."""
    fn_name = message.get("functionCall", {}).get("name", "")
    params = message.get("functionCall", {}).get("parameters", {})

    if fn_name == "search_knowledge":
        query = params.get("query", "")
        from app.rag import search_knowledge

        results = search_knowledge(query, top_k=3)
        result_text = "\n".join(
            f"- {r['subject']}/{r['topic']}: {r['text'][:200]}" for r in results
        )
        return JSONResponse(
            content={"result": result_text or "No relevant results found."}
        )

    return JSONResponse(content={"result": "Unknown function."})


def _handle_conversation_update(message: dict):
    """Track conversation turns for context."""
    call_id = message.get("call", {}).get("id", "")
    conversation = message.get("conversation", [])
    if call_id and conversation:
        conversations[call_id] = [
            {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            for msg in conversation
            if msg.get("content")
        ]


def _chat_response(text: str):
    """Return an OpenAI-compatible chat completion response."""
    return JSONResponse(
        content={
            "id": "eduvoice-response",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=int(PORT), reload=True)
