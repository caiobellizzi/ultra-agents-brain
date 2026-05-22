"""Minimal Telegram Bot API sender — no third-party dependencies."""

from __future__ import annotations

import json
import os
import ssl
import urllib.request


def send_message(text: str, *, chat_id: str | None = None) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    if chat_id is None:
        chat_id = os.getenv("TELEGRAM_ALERT_CHAT_ID", "")
    if not chat_id:
        raise RuntimeError("TELEGRAM_ALERT_CHAT_ID not set")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": "Markdown",
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        import certifi
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ssl_ctx) as resp:
        resp.read()
