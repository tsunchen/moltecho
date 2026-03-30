#!/usr/bin/env python3
"""
Send TTS audio file to Feishu private chat using requests library.

Usage:
    python3 send_voice_to_feishu.py <audio_file> <user_open_id>

Credentials are read from:
    - Environment variables (FEISHU_APP_ID, FEISHU_APP_SECRET) if set
    - Config file: {workspace}/memory/feishu_credentials.json
"""

import os
import sys
import json
import requests

def find_workspace():
    """Find the correct workspace directory."""
    # Priority: Check for feishu_credentials.json (primary config file)
    env_workspace = os.environ.get('WORKSPACE_DIR')
    if env_workspace and os.path.isdir(env_workspace):
        config_path = os.path.join(env_workspace, 'memory', 'feishu_credentials.json')
        if os.path.isfile(config_path):
            return env_workspace
    
    script_path = os.path.abspath(__file__)
    
    # Search for agents/*/workspace/memory/feishu_credentials.json
    openclaw_idx = script_path.find('/.openclaw/')
    if openclaw_idx > 0:
        openclaw_root = script_path[:openclaw_idx + len('/.openclaw')]
        agents_dir = os.path.join(openclaw_root, 'agents')
        if os.path.isdir(agents_dir):
            for agent in os.listdir(agents_dir):
                agent_workspace = os.path.join(agents_dir, agent, 'workspace')
                config_path = os.path.join(agent_workspace, 'memory', 'feishu_credentials.json')
                if os.path.isfile(config_path):
                    return agent_workspace
    
    # Fallback: check if current workspace has the config
    candidate = os.path.dirname(os.path.dirname(os.path.dirname(script_path)))
    config_path = os.path.join(candidate, 'memory', 'feishu_credentials.json')
    if os.path.isfile(config_path):
        return candidate
    
    # Final fallback
    return os.path.dirname(os.path.dirname(os.path.dirname(script_path)))


# Get workspace directory
WORKSPACE_DIR = find_workspace()

# Try environment variables first, then config file
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET_KEY = os.environ.get("FEISHU_APP_SECRET", "")

if not APP_ID or not APP_SECRET_KEY:
    config_path = os.environ.get(
        "FEISHU_CONFIG_PATH",
        os.path.join(WORKSPACE_DIR, 'memory', 'feishu_credentials.json')
    )
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            APP_ID = config.get("app_id", "")
            APP_SECRET_KEY = config.get("app_secret", "")
    except Exception as e:
        print(f"Warning: Could not load config from {config_path}: {e}")


def get_tenant_token():
    if not APP_ID or not APP_SECRET_KEY:
        raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET must be set")
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
    user_id = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("DEFAULT_USER_ID", "")

    msg_id = upload_and_send(audio_path, user_id)
    print(f"Voice message sent: {msg_id}")
