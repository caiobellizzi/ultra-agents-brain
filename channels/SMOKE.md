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

## Expected approval payload

When a run is paused for HITL approval, AgentOS returns JSON with this shape:

```json
{
  "status": "PAUSED",
  "run_id": "<uuid>",
  "approval_id": "<uuid>",
  "approval_prompt": "Trust-gate: write note to vault (source=https://anthropic.com). Approve?"
}
```

| Field            | Type   | Description                                              |
|------------------|--------|----------------------------------------------------------|
| `status`         | string | Must be `"PAUSED"` for HITL flow to trigger             |
| `run_id`         | string | The Agno run UUID — used in `/agents/{id}/runs/{run_id}/continue` |
| `approval_id`    | string | The approval UUID — used in `/approvals/{id}/resolve`   |
| `approval_prompt`| string | Human-readable description of what requires approval     |

Compare real AgentOS responses against this during smoke to catch schema drift.
If `approval_id` or `run_id` are missing, the adapter will surface empty strings
and the continue call will 404 — update `trust_gate.py` to include them.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| Bot does not reply | Check `TELEGRAM_BOT_TOKEN`; check adapter logs for errors |
| `Network error reaching AgentOS` | AgentOS not running on `:7001` |
| `AgentOS error: 422` | Request shape mismatch — check form-data fields in adapter |
| No approve/deny buttons | `status` field name differs from `"PAUSED"` — inspect raw AgentOS JSON |
| `AgentOS error: 404` on continue | `run_id` or `agent_id` wrong — check approval payload |
