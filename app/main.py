"""EduVoice — Voice-First Learning Assistant.

FastAPI server that handles Vapi webhook events for a voice-based
educational RAG agent powered by Qdrant + OpenAI.
"""

import os
import json
import time
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from app.config import HOST, PORT
from app.rag import generate_answer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("eduvoice")

app = FastAPI(title="EduVoice", version="1.0.0")


@app.middleware("http")
async def add_cross_origin_isolation_headers(request: Request, call_next):
    """Enable SharedArrayBuffer for Vapi's Krisp noise-suppression WASM worker."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response


STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

# In-memory conversation store (keyed by call ID)
conversations: dict[str, list[dict]] = {}


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the landing page with Vapi keys injected."""
    html_path = os.path.join(STATIC_DIR, "index.html")
    with open(html_path) as f:
        html = f.read()
    html = html.replace("{{VAPI_PUBLIC_KEY}}", os.getenv("VAPI_PUBLIC_KEY", ""))
    html = html.replace("{{VAPI_ASSISTANT_ID}}", os.getenv("VAPI_ASSISTANT_ID", ""))
    return HTMLResponse(content=html)


@app.get("/health")
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

    if msg_type == "transcript":
        role = message.get("role", "?")
        transcript = message.get("transcript", "")
        ttype = message.get("transcriptType", "")
        if ttype == "final":
            if role == "user":
                log.info(f"🎤 STT (user said): {transcript}")
            else:
                log.info(f"🔊 TTS (bot said): {transcript}")
        return JSONResponse(content={"status": "ok"})

    if msg_type == "speech-update":
        status = message.get("status", "")
        role = message.get("role", "")
        log.info(f"🗣️  Speech {status} ({role})")
        return JSONResponse(content={"status": "ok"})

    if msg_type == "assistant-request":
        log.info("🤖 Assistant config requested")
        return _handle_assistant_request()

    if msg_type == "function-call":
        return await _handle_function_call(message)

    if msg_type == "conversation-update":
        _handle_conversation_update(message)
        return JSONResponse(content={"status": "ok"})

    if msg_type == "end-of-call-report":
        call_id = message.get("call", {}).get("id", "")
        ended_reason = message.get("endedReason", "unknown")
        log.info(f"📴 Call ended: {call_id} | reason: {ended_reason}")
        summary = message.get("summary")
        if summary:
            log.info(f"   Summary: {summary}")
        conversations.pop(call_id, None)
        return JSONResponse(content={"status": "ok"})

    if msg_type == "status-update":
        status = message.get("status", "")
        ended_reason = message.get("endedReason", "")
        if ended_reason:
            log.warning(f"📞 Call status: {status} | ended reason: {ended_reason}")
        else:
            log.info(f"📞 Call status: {status}")
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


@app.post("/vapi/chat/completions")
async def vapi_chat(request: Request):
    """Custom LLM endpoint for Vapi.

    Vapi sends OpenAI-compatible chat completion requests here.
    We intercept the user message, run RAG, and return the response.
    """
    body = await request.json()
    messages = body.get("messages", [])
    call_id = body.get("call", {}).get("id", "unknown")
    stream = body.get("stream", False)

    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        log.warning("⚠️  No user message in chat request")
        answer = "I didn't catch that. Could you repeat your question?"
    else:
        log.info(f"❓ User query: {user_message}")
        history = conversations.get(call_id, [])
        answer = generate_answer(user_message, conversation_history=history)
        log.info(f"💬 Bot answer: {answer}")
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": answer})
        conversations[call_id] = history

    if stream:
        return StreamingResponse(
            _stream_chat_chunks(answer),
            media_type="text/event-stream",
        )
    return _chat_response(answer)


def _stream_chat_chunks(text: str):
    """Yield OpenAI-compatible SSE chunks for streaming."""
    chunk_id = f"chatcmpl-{int(time.time() * 1000)}"
    created = int(time.time())
    base = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": "eduvoice-rag",
    }

    # Opening chunk with role
    first = {**base, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
    yield f"data: {json.dumps(first)}\n\n"

    # Stream text in word-sized chunks
    words = text.split(" ")
    for i, word in enumerate(words):
        content = word if i == 0 else " " + word
        chunk = {**base, "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}
        yield f"data: {json.dumps(chunk)}\n\n"

    # Closing chunk
    done = {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    yield f"data: {json.dumps(done)}\n\n"
    yield "data: [DONE]\n\n"


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
