# EduVoice — Voice-First Learning Assistant

A voice-first AI agent that helps students learn through natural conversation. Built with **Vapi** (voice AI), **Qdrant** (vector search), and **OpenAI** (embeddings + LLM).

Students can call and ask questions about any subject — physics, chemistry, math, biology, history, computer science, and more. The agent retrieves relevant knowledge, generates clear spoken explanations, and maintains conversation context.

## Architecture

```
Student speaks → Vapi (STT) → FastAPI Server
    → Embed query (OpenAI) → Qdrant semantic search
    → Retrieved context + query → LLM (RAG)
    → Response text → Vapi (TTS) → Student hears answer
```

## Tech Stack

- **Vapi** — Voice interface (speech-to-text, text-to-speech, call management)
- **Qdrant** — Vector database for semantic knowledge retrieval
- **OpenAI** — Embeddings (`text-embedding-3-small`) + LLM (`gpt-4o-mini`)
- **FastAPI** — Python backend server
- **ngrok** — Tunnel local server for Vapi webhooks

## Setup

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

You need:
- **Vapi API Key** — from dashboard.vapi.ai
- **Qdrant Cloud URL + API Key** — from cloud.qdrant.io (free tier)
- **OpenAI API Key** — from platform.openai.com

### 3. Seed the knowledge base

```bash
python scripts/seed_knowledge.py
```

This embeds 25+ educational documents into Qdrant across physics, chemistry, math, biology, history, geography, computer science, and English.

### 4. Start the server

```bash
python -m app.main
```

### 5. Expose with ngrok

```bash
ngrok http 8000
```

### 6. Create the Vapi assistant

```bash
python scripts/setup_vapi.py https://your-ngrok-url.ngrok.io
```

### 7. Test

Go to **dashboard.vapi.ai** → find "EduVoice" → click **Talk** to test via browser.

## Features

- **RAG-powered answers** — retrieves relevant knowledge before answering
- **Multi-subject** — physics, chemistry, math, biology, history, CS, and more
- **Conversation memory** — maintains context across turns within a call
- **Multilingual** — responds in the same language the student speaks (Hindi, English, etc.)
- **Voice-optimized** — concise, spoken-friendly responses
- **Encouraging tone** — patient and supportive for learners

## Project Structure

```
Voice-Agent/
├── app/
│   ├── __init__.py
│   ├── config.py          # Environment config
│   ├── main.py            # FastAPI server + Vapi endpoints
│   └── rag.py             # RAG pipeline (Qdrant + OpenAI)
├── scripts/
│   ├── seed_knowledge.py  # Populate Qdrant with knowledge
│   ├── setup_vapi.py      # Create Vapi assistant
│   └── test_call.py       # List/test assistants
├── data/
│   └── knowledge.json     # Educational knowledge base
├── requirements.txt
├── .env.example
└── README.md
```

## Hackathon

Built for the Voice AI Hackathon — Track 3: Accessibility & Societal Impact (Education).
