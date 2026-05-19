# Telegram Adapter — Manual Smoke Test

Run these steps after Wave 3 is committed. You need two terminals.

## Prerequisites

- `.env` filled: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS` (your chat ID),
  `LITELLM_MASTER_KEY`, `LM_STUDIO_API_BASE`, `LM_STUDIO_MODEL`.
- LiteLLM proxy running on `:4000` (or your configured port).
- LM Studio running and serving the configured model.

---

## Terminal A — AgentOS

```bash
cd /path/to/ultra-agents-brain
source .venv/bin/activate
python -m agentos
```

Expected: Uvicorn starts on `http://127.0.0.1:7001`. You should see
`Application startup complete.` with 5 agents registered.

Quick health check (optional):
```bash
curl -s http://127.0.0.1:7001/health | python3 -m json.tool
```

---

## Terminal B — Telegram adapter

```bash
cd /path/to/ultra-agents-brain
source .venv/bin/activate
python -m channels.telegram_adapter
```

Expected: `[telegram-adapter] INFO Starting. Allowed chat IDs: {<your_id>}`

---

## Smoke tests in Telegram

### Basic chat

Send to `@ultra_agents_brain_bot`:
```
hi
```

Expected: A short reply from the chat agent (may cite the vault or answer from general knowledge).

### Ingest (triggers HITL approval)

```
/ingest https://anthropic.com
```

Expected:
1. Bot replies with an approval prompt message.
2. Two inline buttons appear: `✅ Approve` and `❌ Deny`.
3. Press `✅ Approve`.
4. Bot follows up with a vault path (e.g. `00-Inbox/anthropic-com.md`).

### Query

```
/query what is in my vault about Anthropic?
```

Expected: A reply summarising any matching notes in the vault.

### Research

```
/research Agno framework Python
```

Expected: A research summary reply.

---

## Expected HITL payload (Agno native contract)

When a run is paused for HITL approval, AgentOS returns JSON with this shape
(non-stream path, `stream=false`):

```json
{
  "status": "PAUSED",
  "run_id": "<uuid>",
  "requirements": [
    {
      "id": "<uuid>",
      "created_at": "2026-...",
      "tool_execution": {
        "tool_call_id": "686188173",
        "tool_name": "ingest_to_vault",
        "tool_args": {"source": "https://anthropic.com"},
        "requires_confirmation": true,
        "confirmed": null,
        "result": null
      }
    }
  ],
  "tools": [
    {
      "tool_call_id": "686188173",
      "tool_name": "ingest_to_vault",
      "requires_confirmation": true,
      ...
    }
  ]
}
```

| Field                               | Type    | Description                                                        |
|-------------------------------------|---------|--------------------------------------------------------------------|
| `status`                            | string  | `"PAUSED"` (uppercase) — the adapter checks this                  |
| `run_id`                            | string  | Run UUID — used in `/agents/{id}/runs/{run_id}/continue`           |
| `requirements`                      | list    | One entry per HITL requirement pending resolution                  |
| `requirements[].tool_execution`     | dict    | The paused tool call                                               |
| `tool_execution.tool_call_id`       | string  | Echoed back in the continue body                                   |
| `tool_execution.tool_name`          | string  | Name of the tool requiring confirmation                            |
| `tool_execution.tool_args`          | dict    | Arguments the LLM passed to the tool                              |
| `tool_execution.requires_confirmation` | bool | `true` = render approve/deny buttons                              |

Note: `is_paused` and `active_requirements` are Python properties on `RunOutput` and
are NOT serialized into the response. Use `status == "PAUSED"` and `requirements[]`.

### Resume request (POST /agents/{agent_id}/runs/{run_id}/continue)

Sent as form-data:

```
updated_tools = [{"tool_call_id": "686188173", "confirmed": true}]
stream        = false
session_id    = telegram-<chat_id>
user_id       = <tg_user_id>
```

`updated_tools` is a JSON-encoded string (not nested JSON). Each entry in the list
maps a `tool_call_id` to a `confirmed` boolean (true=approve, false=deny).

The old `/approvals/{id}/resolve` endpoint is the AgentOS dashboard's approval table
and is NOT part of this flow — do not call it from the adapter.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| Bot does not reply | Check `TELEGRAM_BOT_TOKEN`; check adapter logs for errors |
| `Network error reaching AgentOS` | AgentOS not running on `:7001` |
| `AgentOS error: 422` | Request shape mismatch — check form-data fields in adapter |
| No approve/deny buttons | `status` field name differs from `"PAUSED"` — inspect raw AgentOS JSON |
| `AgentOS error: 404` on continue | `run_id` or `agent_id` wrong — check approval payload |
