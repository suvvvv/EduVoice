"""Make a test web call to the EduVoice assistant via Vapi API."""

import sys
import os
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import VAPI_API_KEY

VAPI_BASE = "https://api.vapi.ai"


def list_assistants():
    """List all assistants to find the EduVoice one."""
    headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}
    resp = httpx.get(f"{VAPI_BASE}/assistant", headers=headers, timeout=30)
    if resp.status_code == 200:
        assistants = resp.json()
        for a in assistants:
            print(f"  {a['id']} — {a.get('name', 'unnamed')}")
        return assistants
    else:
        print(f"Error: {resp.status_code} {resp.text}")
        return []


if __name__ == "__main__":
    print("Your Vapi Assistants:")
    list_assistants()
