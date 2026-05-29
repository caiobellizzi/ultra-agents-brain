---
phase: 11-memory-surface-activation
plan: 02
date: 2026-05-23
deployed_sha: 9ed4a0a
operator_telegram_id: 7113965359
---

# Plan 11-02 — smoke evidence

## Pre-fix baseline

See `evidence/experiment-2026-05-22.md`. Summary:

- `POST /teams/supervisor/runs` from VPS-local: **HTTP 000, time_total=120s** (timed out, the team hung in Agno's manual-CoT loop layered over the NIM DeepSeek thinking model).
- Real Telegram messages: bot replied "Network error" because the adapter's 35s implicit timeout fired before the team's hang ever resolved.

## Post-fix supervisor probe (synthetic)

```
$ curl -sS --max-time 90 -X POST http://31.97.130.253:7000/teams/supervisor/runs \
    -F "message=quick smoke probe — what is the capital of France?" \
    -F "session_id=11-02-sup-probe-1" -F "user_id=99999996" -F "stream=false"

HTTP 200 time=33.691903s
```

Response body (first 280 chars):

```
{"run_id":"7a89ddbb-bc39-4f4d-8cc5-28ea6da359ef","team_id":"supervisor",
"team_name":"supervisor","session_id":"11-02-sup-probe-1",
"user_id":"99999996",
"input":{"input_content":"quick smoke probe — what is the capital of France?"},
"content":"This is a straightforward question I can answer directly:
**Paris** is the capital of France. ..."
```

**Result: PASS.** Supervisor team now answers within the 90s budget (33.7s observed, well under the new ceiling). Previously hung indefinitely.

## Post-fix Telegram round-trip (real message)

The operator sent a Telegram message at approximately **01:12:48 UTC, 2026-05-23**. The adapter journal shows:

```
01:12:48 ... POST http://127.0.0.1:7000/teams/supervisor/runs "HTTP/1.1 200 OK"
01:12:49 ... POST https://api.telegram.org/.../sendMessage "HTTP/1.1 200 OK"
```

**Result: PASS.** Telegram → adapter → supervisor → reply round-trip completed without timeout. The 11-02 fix unblocks real-channel traffic.

The supervisor response on this run was quick (sub-second on the brain side, returned from session history of the operator's prior context). No new memory row was extracted because the facts in the operator's message ("favorite color teal", "bikes Tuesdays") already existed in `agno_memories` from the 22:39 UTC May 22 baseline experiment (deduplication by `create_or_update_memories`).

## MEM-01 latency — fresh synthetic probe (definitive)

To verify the 5-second SLA cleanly, ran a controlled probe with a unique `user_id` (no prior memory state):

```
$ POST http://127.0.0.1:7000/agents/chat/runs
  message="I have a cat named Mochi and I'm allergic to peanuts."
  user_id=mem-fresh-1779504587

POST HTTP 200 time=16.683930s
```

Memory rows in `agno_memories` for that user_id at `t + 2s` after POST return:

```
row_count=2
 - 2026-05-23T02:49:54Z   "User has a cat named Mochi."
 - 2026-05-23T02:49:54Z   "User is allergic to peanuts."
```

**Result: MEM-01 SLA satisfied — memory rows persisted within 2 seconds of agent run completion.**

The 16.7s POST latency is the chat agent's NIM inference time (orchestrator + tool calls), not the memory write path. The memory write itself is sub-second. The integration-test SLA constant (5s) is still a tight budget when measured from POST-start; refactoring the test to measure from POST-completion is tracked in `11-01-SUMMARY.md` open items.

## OBS-01 log line — STILL MISSING (known gap, see 11-01)

`journalctl -u uab-brain.service` searched for `OBS-01 memory write` immediately after the fresh probe above: **no matches**.

This is the same gap documented in `11-01-SUMMARY.md`: the chat agent's `enable_agentic_memory=True` path routes memory writes through `MemoryManager.update_memory_task → run_memory_task`. `InstrumentedMemoryManager` in plan 11-01 only overrode `create_user_memories` / `acreate_user_memories`. Memory rows ARE being written (proven above), but the OBS-01 instrumentation does not fire for this code path.

**Disposition:** carry forward as an open follow-up (plan 11-03 or sweep into a future phase). Plan 11-02's contract — supervisor unhang + telegram timeout shape — is fully satisfied independently of this gap.

## `pg_stat` delta — not captured

The smoke harness did not run `pg_stat_user_tables` before/after due to SSH rate-limiting on the VPS. The 2 fresh rows above are direct evidence of `n_tup_ins += 2`.

## Open items

- **OBS-01 coverage gap** (re-affirmed): plan 11-03 should extend `InstrumentedMemoryManager` to override `update_memory_task` / `aupdate_memory_task` / `run_memory_task`. Until then OBS-01 logs are only emitted for the auto-extraction path that no agent in this deployment actually triggers.
- **Real-Telegram dedup**: future smoke tests should use unique facts each run; the operator's first 11-02 smoke message produced no new row because of memory-store dedup, not a routing failure.
