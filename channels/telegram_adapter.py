"""Telegram long-poll adapter — bridges Telegram <-> AgentOS.

Run with:
    python -m channels.telegram_adapter

Environment variables (required):
    TELEGRAM_BOT_TOKEN          — BotFather token
    TELEGRAM_ALLOWED_CHAT_IDS   — comma-separated integer chat IDs

Environment variables (optional):
    AGENTOS_BASE_URL            — default http://127.0.0.1:7000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

# In-memory cache of paused tool_execution dicts, keyed by run_id.
# Needed because Agno's /continue endpoint REPLACES run_response.tools with the
# payload, so we must echo back the full original dict plus `confirmed`.
_PAUSED_TOOLS: dict[str, list[dict]] = {}
# Tracks run_ids that have already been resolved (approved or denied) to
# silently drop duplicate callback events (e.g. double-tap on Approve).
_RESOLVED_RUNS: set[str] = set()

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
_open_to_all = os.getenv("TELEGRAM_OPEN_TO_ALL", "").lower() in ("1", "true", "yes")
if not ALLOWED_CHAT_IDS and not _open_to_all:
    raise RuntimeError(
        "TELEGRAM_ALLOWED_CHAT_IDS is empty and TELEGRAM_OPEN_TO_ALL is not set. "
        "Set TELEGRAM_ALLOWED_CHAT_IDS=<chat_id,...> or TELEGRAM_OPEN_TO_ALL=1."
    )

AGENTOS_BASE_URL: str = os.getenv("AGENTOS_BASE_URL", "http://127.0.0.1:7000")
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


def _format_tool_args(args: dict) -> str:
    """Return a short human-readable summary of tool args."""
    if not args:
        return "(no args)"
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 80:
            v_str = v_str[:77] + "..."
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)


def extract_reply_text(agent_response: dict) -> str:
    """Extract human-readable text from typed agent response."""
    output = agent_response.get("output", {})

    if isinstance(output, dict):
        # ChatReply / QueryAnswer
        if "text" in output:
            return output["text"]
        if "answer" in output:
            return output["answer"]
        # ResearchReport
        if "findings" in output:
            findings = output["findings"]
            text = "\n".join(f"• {f['summary']}" for f in findings[:5])
            if output.get("next_questions"):
                text += "\n\nNext questions:\n" + "\n".join(
                    f"• {q}" for q in output["next_questions"][:3]
                )
            return text
        # CuratorResult / IngestResult — not user-facing in Telegram
        if "actions_taken" in output:
            return f"Done: {', '.join(output['actions_taken'][:3])}"
        if "note_path" in output:
            return f"Ingested → {output['note_path']}"

    # Fallback: stringify whatever we got
    return str(output)


def format_citations(citations: list[dict]) -> str:
    if not citations:
        return ""
    lines = ["_Sources:_"]
    for c in citations[:3]:
        title = c.get("title", c.get("path", ""))
        lines.append(f"• {title}")
    return "\n\n" + "\n".join(lines)


async def send_approval_buttons(
    client: httpx.AsyncClient,
    chat_id: int,
    run_id: str,
    agent_id: str,
    requirements: list[dict],
) -> None:
    """Render inline approve/deny keyboard for each paused tool call.

    Agno PAUSED response includes a `requirements` array. Each entry has a
    nested `tool_execution` dict with tool_call_id, tool_name, tool_args, and
    requires_confirmation. We render one approve/deny row per requirement that
    has requires_confirmation=True.
    """
    keyboard_rows = []
    lines = ["Approval required for the following action(s):"]
    cached_tools: list[dict] = []

    for req in requirements:
        tool_exec: dict = req.get("tool_execution") or {}
        if not tool_exec.get("requires_confirmation"):
            continue
        cached_tools.append(tool_exec)
        tool_call_id: str = tool_exec.get("tool_call_id", "")
        tool_name: str = tool_exec.get("tool_name", "unknown")
        tool_args: dict = tool_exec.get("tool_args") or {}
        args_summary = _format_tool_args(tool_args)

        lines.append(f"\nTool: {tool_name}\nArgs: {args_summary}")

        keyboard_rows.append([
            {
                "text": "Approve",
                "callback_data": f"approve:{run_id}:{agent_id}:{tool_call_id}",
            },
            {
                "text": "Deny",
                "callback_data": f"deny:{run_id}:{agent_id}:{tool_call_id}",
            },
        ])

    if not keyboard_rows:
        # Paused but nothing to confirm — surface generic message
        await send_message(client, chat_id, "Run paused — no confirmation requirements found.")
        return

    _PAUSED_TOOLS[run_id] = cached_tools
    keyboard = {"inline_keyboard": keyboard_rows}
    await send_message(client, chat_id, "\n".join(lines), reply_markup=keyboard)


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
    return "supervisor"


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

    if agent_id == "supervisor":
        url = f"{AGENTOS_BASE_URL}/teams/{agent_id}/runs"
    else:
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
    log.debug("AgentOS run response: %s", payload)

    # Agno HITL: status is "PAUSED" (uppercase) in the non-stream response.
    # is_paused is a property and not serialized. requirements contains the
    # tool executions waiting for confirmation.
    status = payload.get("status", "")
    is_paused = status == "PAUSED" or status == "paused" or payload.get("is_paused") is True

    if is_paused:
        run_id = payload.get("run_id", "")
        # Agno serialises 'requirements' (not 'active_requirements') in to_dict()
        requirements: list[dict] = payload.get("requirements") or []
        log.info("Run %s paused — %d requirement(s)", run_id, len(requirements))
        await send_approval_buttons(client, chat_id, run_id, agent_id, requirements)
    else:
        reply = extract_reply_text(payload)
        output = payload.get("output", {})
        if isinstance(output, dict):
            citations = output.get("citations", [])
            if citations:
                reply += format_citations(citations)
        await send_message(client, chat_id, reply)


async def handle_callback(
    client: httpx.AsyncClient,
    query: dict,
) -> None:
    """Handle inline keyboard callback (approve / deny).

    callback_data format: {action}:{run_id}:{agent_id}:{tool_call_id}
    """
    callback_id: str = query["id"]
    chat_id: int = query["message"]["chat"]["id"]
    tg_user_id: int = query.get("from", {}).get("id", chat_id)
    data: str = query.get("data", "")

    # Acknowledge immediately so the spinner clears
    await tg_post(client, "answerCallbackQuery", callback_query_id=callback_id)

    parts = data.split(":")
    if len(parts) != 4:
        log.warning("Unexpected callback_data shape: %s", data)
        return

    action, run_id, agent_id, tool_call_id = parts

    _VALID_AGENTS = {"chat", "ingest", "query", "research", "curator", "supervisor"}
    _UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    if agent_id not in _VALID_AGENTS:
        log.warning("callback_data contains unknown agent_id %r — ignoring", agent_id)
        return
    if not _UUID_RE.match(run_id):
        log.warning("callback_data contains invalid run_id %r — ignoring", run_id)
        return

    if run_id in _RESOLVED_RUNS:
        log.debug("Ignoring duplicate callback for already-resolved run %s", run_id)
        return
    confirmed = action == "approve"

    # Resume the run via Agno's native /runs/{run_id}/continue endpoint.
    # Agno REPLACES run_response.tools with this list, so we must echo back the
    # full original ToolExecution dicts (tool_name, tool_args, etc.) and just
    # flip `confirmed` on the matched one.
    # Agno's handle_tool_call_updates requires BOTH requires_confirmation=True
    # AND confirmed=True to execute the tool. Setting requires_confirmation=False
    # skips the execution branch entirely. Keep the original flag, just flip
    # `confirmed`.
    cached = _PAUSED_TOOLS.pop(run_id, None)
    if cached:
        tools_list: list[dict] = []
        for t in cached:
            new = dict(t)
            if new.get("tool_call_id") == tool_call_id:
                new["confirmed"] = confirmed
            tools_list.append(new)
    else:
        tools_list = [{
            "tool_call_id": tool_call_id,
            "confirmed": confirmed,
            "requires_confirmation": True,
        }]
    tools_payload = json.dumps(tools_list)
    if agent_id == "supervisor":
        continue_url = f"{AGENTOS_BASE_URL}/teams/{agent_id}/runs/{run_id}/continue"
    else:
        continue_url = f"{AGENTOS_BASE_URL}/agents/{agent_id}/runs/{run_id}/continue"
    continue_data = {
        "tools": tools_payload,
        "stream": "false",
        "session_id": f"telegram-{chat_id}",
        "user_id": str(tg_user_id),
    }

    try:
        r = await client.post(continue_url, data=continue_data)
    except httpx.RequestError as exc:
        log.error("Network error resuming run: %s", exc)
        await send_message(client, chat_id, "Network error resuming run.")
        return

    if r.status_code not in (200, 201):
        log.warning("Continue returned %s: %s", r.status_code, r.text[:200])
        await send_message(client, chat_id, f"AgentOS error resuming run: {r.status_code}")
        return

    _RESOLVED_RUNS.add(run_id)

    if not confirmed:
        await send_message(client, chat_id, "Action denied.")
        return

    payload = r.json()
    reply = extract_reply_text(payload)
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
