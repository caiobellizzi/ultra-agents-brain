"""Minimal Telegram bot for triggering ultra-agents-brain commands.

Long-polls Telegram getUpdates and runs whitelisted slash commands as subprocess.
Authorized via TELEGRAM_ALLOWED_CHAT_IDS (comma-separated) or TELEGRAM_ALERT_CHAT_ID.

Run as systemd service uab-bot.service.
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from .telegram import send_message


# Slash command → ultra_brain CLI args (vault is appended separately)
COMMANDS: dict[str, list[str]] = {
    "/brief": ["daily-brief"],
    "/monitor": ["monitor", "--feeds", "skills/worker.monitor/feeds.txt"],
    "/bluesky": ["bluesky", "--handles", "skills/worker.monitor/bluesky-handles.txt"],
}

_HELP = (
    "ultra-agents-brain commands:\n"
    "/brief — generate today's daily brief\n"
    "/monitor — poll RSS feeds now\n"
    "/bluesky — poll Bluesky handles now\n"
    "/help — show this list"
)


def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _get_updates(token: str, offset: int, timeout: int = 25) -> list[dict]:
    params = urllib.parse.urlencode({"timeout": timeout, "offset": offset})
    url = f"https://api.telegram.org/bot{token}/getUpdates?{params}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout + 10, context=_ssl_ctx()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("result", [])


def _run_command(args: list[str], project_root: str, vault: str, timeout: int = 600) -> str:
    cmd = [
        f"{project_root}/.venv/bin/python", "-m", "ultra_brain",
        "--vault", vault,
    ] + args
    try:
        result = subprocess.run(
            cmd, cwd=project_root, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            return f"❌ exit {result.returncode}\n{(result.stderr or result.stdout)[-1000:]}"
        return f"✅ {(result.stdout or '(no output)').strip()[-2000:]}"
    except subprocess.TimeoutExpired:
        return f"⏰ timed out after {timeout}s"
    except Exception as exc:
        return f"❌ error: {exc}"


def _load_allowed_chats() -> set[int]:
    allowed: set[int] = set()
    for piece in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(","):
        piece = piece.strip()
        if piece:
            try:
                allowed.add(int(piece))
            except ValueError:
                pass
    alert = os.getenv("TELEGRAM_ALERT_CHAT_ID", "").strip()
    if alert:
        try:
            allowed.add(int(alert))
        except ValueError:
            pass
    return allowed


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return 1

    allowed = _load_allowed_chats()
    if not allowed:
        print("No authorized chat IDs in TELEGRAM_ALLOWED_CHAT_IDS or TELEGRAM_ALERT_CHAT_ID", file=sys.stderr)
        return 1

    project_root = os.getenv("UAB_PROJECT_ROOT", "/opt/ultra-agents-brain")
    vault = os.getenv("UAB_VAULT", "/srv/second-brain")
    print(f"uab-bot: ready (allowed={allowed}, vault={vault})", flush=True)

    offset = 0
    while True:
        try:
            updates = _get_updates(token, offset)
        except Exception as exc:
            print(f"uab-bot: getUpdates failed: {exc}", file=sys.stderr)
            time.sleep(10)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            text = (msg.get("text") or "").strip()

            if chat_id is None or not text.startswith("/"):
                continue
            if chat_id not in allowed:
                print(f"uab-bot: rejected unauthorized chat_id={chat_id}", file=sys.stderr)
                continue

            cmd_word = text.split()[0].split("@")[0]  # strip @botname suffix

            if cmd_word == "/help" or cmd_word == "/start":
                send_message(_HELP, chat_id=str(chat_id))
                continue

            args = COMMANDS.get(cmd_word)
            if args is None:
                send_message(f"Unknown command: {cmd_word}\nSend /help for list.", chat_id=str(chat_id))
                continue

            send_message(f"▶️ Running `{cmd_word}`...", chat_id=str(chat_id))
            result = _run_command(args, project_root, vault)
            send_message(f"`{cmd_word}` result:\n{result}", chat_id=str(chat_id))


if __name__ == "__main__":
    raise SystemExit(main())
