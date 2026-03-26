#!/usr/bin/env python3
"""
Send TTS audio file to Feishu private chat using requests library.

Usage:
    python3 send_voice_to_feishu.py <audio_file> <user_open_id>
"""

import sys
import json
import requests
import os

APP_ID = "cli_a90466cb86f85bc8"
APP_SECRET_KEY = "FyQykHiyanqeZqhLM51s7fbl44R3kzrx"


def get_tenant_token():
    r = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET_KEY},
        timeout=10
    )
    return r.json().get("tenant_access_token", "")


def upload_and_send(audio_path: str, user_open_id: str) -> str:
    """Upload audio and send to user. Returns message_id."""
    token = get_tenant_token()

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # Upload audio file
    r = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/files",
        data={"file_type": "opus"},
        files={"file": ("voice.wav", audio_data, "audio/wav")},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15
    )
    result = r.json()
    if result.get("code") != 0:
        raise Exception(f"Upload failed: {result}")
    file_key = result["data"]["file_key"]

    # Send audio message
    r2 = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        json={
            "receive_id": user_open_id,
            "msg_type": "audio",
            "content": json.dumps({"file_key": file_key})
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=10
    )
    msg_result = r2.json()
    if msg_result.get("code") != 0:
        raise Exception(f"Send failed: {msg_result}")
    return msg_result["data"]["message_id"]


if __name__ == "__main__":
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/tts_output.wav"
    user_id = sys.argv[2] if len(sys.argv) > 2 else "ou_491f83d2cb22d22e94cab10f6f43e87e"

    msg_id = upload_and_send(audio_path, user_id)
    print(f"Voice message sent: {msg_id}")
