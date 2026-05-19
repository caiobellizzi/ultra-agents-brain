"""Telegram long-poll adapter — bridges Telegram <-> AgentOS.

Run with:
    python -m channels.telegram_adapter

Environment variables (required):
    TELEGRAM_BOT_TOKEN          — BotFather token
    TELEGRAM_ALLOWED_CHAT_IDS   — comma-separated integer chat IDs

Environment variables (optional):
    AGENTOS_BASE_URL            — default http://127.0.0.1:7001
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[telegram-adapter] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
_raw_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS: set[int] = (
    {int(x.strip()) for x in _raw_ids.split(",") if x.strip()}
    if _raw_ids.strip()
    else set()
)
AGENTOS_BASE_URL: str = os.getenv("AGENTOS_BASE_URL", "http://127.0.0.1:7001")
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_TIMEOUT = 30  # seconds for long-poll


# ---------------------------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------------------------


async def tg_get(client: httpx.AsyncClient, method: str, **params: Any) -> dict:
    resp = await client.get(f"{TG_API}/{method}", params=params)
    resp.raise_for_status()
    return resp.json()


async def tg_post(client: httpx.AsyncClient, method: str, **payload: Any) -> dict:
    resp = await client.post(f"{TG_API}/{method}", json=payload)
    resp.raise_for_status()
    return resp.json()


async def send_message(
    client: httpx.AsyncClient,
    chat_id: int,
    text: str,
    reply_markup: dict | None = None,
) -> None:
    kwargs: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        kwargs["reply_markup"] = reply_markup
    await tg_post(client, "sendMessage", **kwargs)


async def send_approval_buttons(
    client: httpx.AsyncClient,
    chat_id: int,
    approval_id: str,
    run_id: str,
    agent_id: str,
    prompt: str,
) -> None:
    """Render inline approve/deny keyboard for a PAUSED run."""
    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "Approve",
                    "callback_data": f"approve:{approval_id}:{run_id}:{agent_id}",
                },
                {
                    "text": "Deny",
                    "callback_data": f"deny:{approval_id}:{run_id}:{agent_id}",
                },
            ]
        ]
    }
    await send_message(
        client,
        chat_id,
        f"Approval required:\n{prompt}\n\nApprove or deny?",
        reply_markup=keyboard,
    )


# ---------------------------------------------------------------------------
# AgentOS helpers
# ---------------------------------------------------------------------------


def _agent_id_for(text: str) -> str:
    """Map message text to an AgentOS agent ID."""
    lower = text.strip().lower()
    if lower.startswith("/ingest "):
        return "ingest"
    if lower.startswith("/query "):
        return "query"
    if lower.startswith("/research "):
        return "research"
    return "chat"


def _message_body(text: str, agent_id: str) -> str:
    """Strip the command prefix to get the actual message content."""
    prefixes = {
        "ingest": "/ingest ",
        "query": "/query ",
        "research": "/research ",
    }
    prefix = prefixes.get(agent_id)
    if prefix and text.strip().lower().startswith(prefix):
        return text.strip()[len(prefix):]
    return text.strip()


async def route_message(
    client: httpx.AsyncClient,
    text: str,
    chat_id: int,
    user_id: int,
) -> None:
    """Route an incoming Telegram message to the correct AgentOS agent."""
    agent_id = _agent_id_for(text)
    body = _message_body(text, agent_id)
    session_id = f"telegram-{chat_id}"

    url = f"{AGENTOS_BASE_URL}/agents/{agent_id}/runs"
    data = {
        "message": body,
        "session_id": session_id,
        "user_id": str(user_id),
        "stream": "false",
    }

    try:
        resp = await client.post(url, data=data)
    except httpx.RequestError as exc:
        log.error("Network error posting to AgentOS: %s", exc)
        await send_message(client, chat_id, "Network error reaching AgentOS. Retry later.")
        return

    if resp.status_code not in (200, 201):
        log.warning("AgentOS returned %s for %s", resp.status_code, url)
        await send_message(client, chat_id, f"AgentOS error: {resp.status_code}")
        return

    payload = resp.json()
    status = payload.get("status") or payload.get("run_status", "")

    if status == "PAUSED":
        approval_id = payload.get("approval_id", "")
        run_id = payload.get("run_id", "")
        prompt = payload.get("approval_prompt", "Agent requires approval to proceed.")
        log.info("Run %s paused for approval %s", run_id, approval_id)
        await send_approval_buttons(client, chat_id, approval_id, run_id, agent_id, prompt)
    else:
        reply = (
            payload.get("content")
            or payload.get("message")
            or payload.get("output")
            or str(payload)
        )
        await send_message(client, chat_id, reply)


async def handle_callback(
    client: httpx.AsyncClient,
    query: dict,
) -> None:
    """Handle inline keyboard callback (approve / deny)."""
    callback_id: str = query["id"]
    chat_id: int = query["message"]["chat"]["id"]
    data: str = query.get("data", "")

    # Acknowledge immediately so the spinner clears
    await tg_post(client, "answerCallbackQuery", callback_query_id=callback_id)

    parts = data.split(":")
    if len(parts) != 4:
        log.warning("Unexpected callback_data shape: %s", data)
        return

    action, approval_id, run_id, agent_id = parts
    approved = action == "approve"

    # 1. Resolve the approval
    resolve_url = f"{AGENTOS_BASE_URL}/approvals/{approval_id}/resolve"
    try:
        r = await client.post(resolve_url, json={"approved": approved})
        if r.status_code not in (200, 201):
            log.warning("Approval resolve returned %s", r.status_code)
    except httpx.RequestError as exc:
        log.error("Network error resolving approval: %s", exc)
        await send_message(client, chat_id, "Network error resolving approval.")
        return

    if not approved:
        await send_message(client, chat_id, "Action denied.")
        return

    # 2. Resume the run
    continue_url = f"{AGENTOS_BASE_URL}/agents/{agent_id}/runs/{run_id}/continue"
    try:
        r = await client.post(continue_url, data={"stream": "false"})
    except httpx.RequestError as exc:
        log.error("Network error resuming run: %s", exc)
        await send_message(client, chat_id, "Network error resuming run.")
        return

    if r.status_code not in (200, 201):
        log.warning("Continue returned %s", r.status_code)
        await send_message(client, chat_id, f"AgentOS error resuming run: {r.status_code}")
        return

    payload = r.json()
    reply = (
        payload.get("content")
        or payload.get("message")
        or payload.get("output")
        or str(payload)
    )
    await send_message(client, chat_id, reply)


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------


async def main() -> None:
    log.info("Starting. Allowed chat IDs: %s", ALLOWED_CHAT_IDS or "ALL (warning: open)")
    log.info("AgentOS base URL: %s", AGENTOS_BASE_URL)

    offset = 0

    async with httpx.AsyncClient(timeout=POLL_TIMEOUT + 5) as client:
        while True:
            try:
                result = await tg_get(
                    client,
                    "getUpdates",
                    offset=offset,
                    timeout=POLL_TIMEOUT,
                    allowed_updates=["message", "callback_query"],
                )
                updates = result.get("result", [])
            except Exception as exc:
                log.error("getUpdates error: %s", exc)
                await asyncio.sleep(5)
                continue

            for update in updates:
                offset = update["update_id"] + 1

                if "callback_query" in update:
                    query = update["callback_query"]
                    chat_id = query["message"]["chat"]["id"]
                    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
                        log.warning("Rejected callback from chat_id %s", chat_id)
                        continue
                    try:
                        await handle_callback(client, query)
                    except Exception as exc:
                        log.error("handle_callback error: %s", exc)

                elif "message" in update:
                    msg = update["message"]
                    chat_id: int = msg["chat"]["id"]
                    user_id: int = msg.get("from", {}).get("id", chat_id)
                    text: str = msg.get("text", "").strip()

                    if not text:
                        continue

                    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
                        log.warning("Rejected message from chat_id %s", chat_id)
                        try:
                            await send_message(
                                client,
                                chat_id,
                                "Sorry, this bot is private. You are not authorised.",
                            )
                        except Exception:
                            pass
                        continue

                    try:
                        await route_message(client, text, chat_id, user_id)
                    except Exception as exc:
                        log.error("route_message error: %s", exc)


if __name__ == "__main__":
    asyncio.run(main())
