# Controlled experiment — memory-extraction hypothesis discrimination

**Date:** 2026-05-22 (VPS UTC 22:36–22:46)
**Operator:** caiobellizzi (Telegram numeric id `7113965359`)
**Purpose:** Discriminate hypothesis A (thin traffic) vs B (extraction LLM failing) per `11-RESEARCH.md` §4c.

## Baseline (T0 = 22:36:53 UTC)

```
ai.agno_memories: 1 row (user_id="workshop", agent_id=null, updated_at=1779488755)
pg_stat agno_memories: n_tup_ins=1, n_tup_upd=19
uab-brain.service: active
uab-telegram.service: active
```

## Step 1 — Operator sent a memory-worthy Telegram message

Operator typed in Telegram: *"My favorite color is teal and I bike to work every Tuesday."*

`uab-telegram` journal:
```
22:38:39  GET getUpdates → 200 OK   (message received)
22:39:14  ERROR Network error posting to AgentOS:    ← exactly 35s later
22:39:14  POST sendMessage → 200 OK   (error reply sent to user)
```

35s = `POLL_TIMEOUT + 5 = httpx.AsyncClient(timeout=35)` (see `channels/telegram_adapter.py:62, 455`).

## Step 2 — Direct probe to `chat` agent from VPS-local (synthetic, bypasses Telegram adapter)

```
curl -X POST http://127.0.0.1:7000/agents/chat/runs \
  -F "message=My favorite color is teal and I bike to work every Tuesday." \
  -F "session_id=mem-probe" -F "user_id=7113965359" -F "stream=false"

→ HTTP 200, time_total=10.237s
→ response.content = "Thank you for letting me know! I have updated your preferences..."
```

DB check immediately after:
```
ai.agno_memories: 3 rows
  user_id=7113965359, agent_id=null, updated_at=1779489584   ← NEW
  user_id=7113965359, agent_id=null, updated_at=1779489568   ← NEW
  user_id=workshop,   agent_id=null, updated_at=1779488755   ← original
pg_stat: n_tup_ins=3 (was 1), n_tup_upd=19
```

**Memory extraction works end-to-end.** Two memory rows produced within 10 seconds, both correctly attributed to the operator's Telegram numeric `user_id`.

## Step 3 — Direct probe to `supervisor` team (the Telegram default route)

```
curl --max-time 120 -X POST http://127.0.0.1:7000/teams/supervisor/runs \
  -F "message=quick smoke probe — what is the capital of France?" \
  -F "session_id=sup-probe-1" -F "user_id=99999997" -F "stream=false"

→ curl: (28) Operation timed out after 120002 milliseconds with 0 bytes received
→ HTTP 000 time_total=120.002s
```

DB check after supervisor probe: row count unchanged (still 3 from step 2). Supervisor team **never responded** within 120 seconds. Hard hang, not just slow.

## Conclusions

| Hypothesis | Disposition |
|---|---|
| A (thin traffic / non-memory-worthy content) | **Partial** — true at the chat-agent level (extraction works), but real traffic never reaches it. |
| B (extraction LLM silently failing) | **Falsified.** Extraction LLM works correctly. The chat-agent run produced 2 memory rows in 10s. |
| C (structural gap in Agno config) | **Falsified.** All gates verified set, all writes attributed correctly. |
| **NEW — D (telegram routes default to broken supervisor team + 35s timeout)** | **Confirmed.** Every Telegram non-prefixed message routes to `_agent_id_for()` → `"supervisor"` (channels/telegram_adapter.py:211) → POST `/teams/supervisor/runs` → hangs >120s → httpx 35s timeout fires → user sees "Network error" → message never reaches memory pipeline. |

## What this changes for phase 11

The memory write path is healthy. Phase 11 still needs:

- **DIAG-BL-01** id pin (precondition; trivial).
- **`agent.id` / `team.id`** explicit assignment on factories (silent gap; OBS-01 prerequisite).
- **OBS-01** instrumentation (structured log line per memory write).
- **Curator + ingest** `update_memory_on_run=False` (defense-in-depth).

But phase 11 does NOT need to fix the extraction LLM. It needs to **unblock traffic** to make MEM-01 testable in production, which is a separate sub-issue. Two options:

- **Option X — Fix or replace the supervisor team route.** Investigate why `POST /teams/supervisor/runs` hangs. Likely a team-orchestration bug or a tool that never returns. Out of memory-surface scope per se, but blocks MEM-01.
- **Option Y — Change Telegram default route to `chat`.** A 1-line change in `_agent_id_for()` (`channels/telegram_adapter.py:211`): `return "chat"` instead of `"supervisor"`. Unblocks memory tests immediately without diagnosing the team bug.

**Recommendation: ship Option Y as a phase 11 sub-task** so MEM-01 becomes verifiable. Spawn a separate backlog item (`DIAG-BL-11` — *Supervisor team hangs on basic queries*) for the deeper investigation.

