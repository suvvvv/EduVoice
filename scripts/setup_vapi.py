"""Create the Vapi assistant and configure it to use our server.

Run this AFTER your server is deployed and you have a public URL.
Usage: python scripts/setup_vapi.py <your-server-url>
Example: python scripts/setup_vapi.py https://abc123.ngrok.io
"""

import sys
import os
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import VAPI_API_KEY

VAPI_BASE = "https://api.vapi.ai"


def create_assistant(server_url: str):
    """Create a Vapi assistant that uses our custom LLM endpoint."""

    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    assistant_config = {
        "name": "EduVoice",
        "model": {
            "provider": "custom-llm",
            "url": f"{server_url}/vapi",
            "model": "eduvoice-rag",
        },
        "voice": {
            "provider": "11labs",
            "voiceId": "21m00Tcm4TlvDq8ikWAM",
        },
        "firstMessage": (
            "Hi! I'm EduVoice, your learning assistant. "
            "You can ask me anything about science, math, history, "
            "or any subject. What would you like to learn today?"
        ),
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "multi",
        },
        "serverUrl": f"{server_url}/vapi/webhook",
        "endCallMessage": "Goodbye! Happy learning!",
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
    }

    print("Creating Vapi assistant...")
    resp = httpx.post(
        f"{VAPI_BASE}/assistant",
        headers=headers,
        json=assistant_config,
        timeout=30,
    )

    if resp.status_code == 201:
        data = resp.json()
        print(f"\nAssistant created successfully!")
        print(f"  ID:   {data['id']}")
        print(f"  Name: {data['name']}")
        print(f"\nYou can now test it:")
        print(f"  1. Go to https://dashboard.vapi.ai")
        print(f"  2. Find 'EduVoice' in your assistants")
        print(f"  3. Click 'Talk' to test via browser")
        print(f"\nOr use the web widget — see scripts/create_web_widget.py")
        return data["id"]
    else:
        print(f"Error creating assistant: {resp.status_code}")
        print(resp.text)
        return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_vapi.py <your-public-server-url>")
        print("Example: python scripts/setup_vapi.py https://abc123.ngrok.io")
        sys.exit(1)

    server_url = sys.argv[1].rstrip("/")
    create_assistant(server_url)
