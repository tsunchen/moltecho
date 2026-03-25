#!/usr/bin/env python3
"""
Feishu Message Sender

Sends messages to Feishu chats using the Bot API.
Used by cron tasks when the message tool's card format fails.

Usage:
    python send_feishu_message.py --chat-id CHAT_ID --message "Hello"
    python send_feishu_message.py --chat-id CHAT_ID --file /path/to/message.txt
"""

import requests
import json
import argparse
import os


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """Get tenant access token from Feishu API."""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": app_id, "app_secret": app_secret}
    resp = requests.post(url, headers=headers, json=data)
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"Failed to get token: {result}")
    return result.get("tenant_access_token")


def send_message(token: str, chat_id: str, content: str) -> dict:
    """Send text message to a Feishu chat."""
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    params = {"receive_id_type": "chat_id"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": content})
    }
    resp = requests.post(url, headers=headers, params=params, json=data)
    result = resp.json()
    if result.get("code") != 0:
        raise Exception(f"Failed to send message: {result}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Send message to Feishu chat")
    parser.add_argument("--chat-id", required=True, help="Chat ID (group chat ID)")
    parser.add_argument("--message", help="Message text to send")
    parser.add_argument("--file", help="File containing message text")
    args = parser.parse_args()

    # Read message from file or argument
    if args.file:
        with open(args.file, 'r') as f:
            content = f.read()
    elif args.message:
        content = args.message
    else:
        raise ValueError("Must provide either --message or --file")

    # Get credentials from environment variables
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET environment variables must be set")

    # Get token and send
    token = get_tenant_access_token(app_id, app_secret)
    result = send_message(token, args.chat_id, content)
    print(f"Message sent successfully: {result.get('data', {}).get('message_id', 'N/A')}")


if __name__ == "__main__":
    main()
