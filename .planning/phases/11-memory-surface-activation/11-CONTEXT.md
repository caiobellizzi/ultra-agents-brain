# Phase 11 CONTEXT — Memory Surface Activation

> Locked decisions and constraints for phases 11-01 and 11-02. Read this before executing either plan.
> Drafted 2026-05-22 from `11-RESEARCH.md` + the controlled-experiment evidence at `evidence/experiment-2026-05-22.md`.

## D-01 — Phase requirements

- **MEM-01** — chat-agent run with memory-worthy content → ≥1 new row in `ai.agno_memories` within 5 s, visible in os.agno.com Memory tab.
- **MEM-02** — memory entries scoped per Phase 10 db_id decision (Option A: shared pinned `id="ultra-brain-main"`).
- **MEM-03** — `update_memory_on_run=True` (aliased to `enable_user_memories`) verified active on the agents that should accumulate memory; verified `False` on the agents that should not.
- **OBS-01 (memory path)** — every memory write emits a structured log line: `path=memory`, `agent_id`, `db_id`, `row_id`, `latency_ms`, `status`.

## D-02 — Ground-truth corrections vs the original ROADMAP framing

ROADMAP said the phase is about "enabling memory extraction". The audit + experiment reframed this:

- The extraction path is **already enabled** (confirmed empirically — synthetic POST inserted 2 rows in 10 s under correct `user_id`).
- The reason `agno_memories` is at 1 row is that **real Telegram traffic never reaches the extraction path** (default route → broken supervisor team → httpx timeout).
- Phase 11 therefore has two distinct deliverables: (a) sharpen the write-path quality (id pin, agent.id plumbing, OBS-01, opt-outs), and (b) unblock real traffic so MEM-01 can be verified end-to-end.

## D-03 — Plan split (two atomic plans)

- **11-01 — Memory write-path activation.** Write-path quality. Independent of telegram. Shippable on its own.
- **11-02 — Telegram path unblocker.** Routing/timeout fix that makes MEM-01 testable on real traffic. Depends on nothing in 11-01 except the integration-test harness; can be executed before, after, or in parallel with 11-01 if needed. Recommended order: 11-01 first, then 11-02 so the smoke test in 11-02 can reuse 11-01's `InstrumentedMemoryManager` logging to prove the path fires.

## D-04 — Files allowed to change

### 11-01 (write-path)

- `agentos/app.py` — add `id="ultra-brain-main"` to PostgresDb constructor; possibly wrap `MemoryManager` with `InstrumentedMemoryManager`.
- `agentos/agents/{chat,query,research,supervisor}.py` — add `id="<name>"` to Agent/Team constructor.
- `agentos/agents/{curator,ingest}.py` — add `id="<name>"`; flip `update_memory_on_run=True` → `False`.
- New `agentos/memory.py` (or `agentos/instrumented_memory.py`) — `InstrumentedMemoryManager` subclass.
- New `tests/unit/test_agent_factories.py` — assert `update_memory_on_run` per-factory.
- New `tests/integration/test_memory_surface.py` — synthetic-POST MEM-01 SLA test (`@pytest.mark.live`).
- `pyproject.toml` / `pytest.ini` — register `live` marker if not already present.

### 11-02 (routing/timeout)

- `agentos/agents/supervisor.py` — `reasoning=True` → `reasoning=False` (1 line).
- `channels/telegram_adapter.py` — change `httpx.AsyncClient(timeout=POLL_TIMEOUT + 5)` (line 455) to an explicit `httpx.Timeout` with `connect=10`, `read=90`, `write=10`, `pool=90`. Keep `POLL_TIMEOUT=30` for the Telegram getUpdates long-poll separately.

## D-05 — Files NOT allowed to change in this phase

- `agno/...` (vendor; never edit installed packages).
- `evals/...` (phase 12 territory).
- `agentos/knowledge.py` and any knowledge wiring (phase 13).
- `agentos/tools/...` (phase 14 / approvals territory).
- `ultra_brain/worker/...` (phase 15).
- `.planning/REQUIREMENTS.md` — phase 11 may promote items but only via a deliberate operator step, not as part of plan execution.

## D-06 — Decision: which agents auto-extract memory?

Per `11-RESEARCH.md` §4f + operator review:

| Agent | `update_memory_on_run` after phase 11 | Why |
|---|---|---|
| chat | **True** (unchanged) | Conversational, stable Telegram user_id, primary memory source. |
| query | **True** (unchanged) | Conversational, user-id stable. |
| research | **True** (unchanged) | Conversational, user-id stable. |
| supervisor (team) | **True** (unchanged) | Team-level facts may be memory-worthy. |
| curator | **False** (change from True) | Background processing, no user identity, LLM cost overhead is pure waste. |
| ingest | **False** (change from True) | One-shot bulk operations; user is fronting the message but the conversation isn't "memory worthy" per se. |

## D-07 — Decision: explicit `agent.id` value per factory

Mirror the existing `name="..."` for each. New ids: `chat`, `query`, `research`, `curator`, `ingest`, `supervisor`. These are the same string values the Agno dashboard already references via `/agents/{agent_id}/runs` and `/teams/{team_id}/runs` (proven by the working synthetic POST in the experiment).

## D-08 — Decision: OBS-01 hook point

`InstrumentedMemoryManager(MemoryManager)` — subclass `agno.memory.manager.MemoryManager` with timing + structured logging wrapped around `create_user_memories` and `acreate_user_memories`. Wired in `agentos/app.py` in place of the bare `MemoryManager(...)` call.

Justification (recap from RESEARCH §4e):

- Catches the auto-extraction path (which is what phase 11 is about).
- Doesn't depend on Agno DB internals — survives upgrades.
- Doesn't catch explicit `db.upsert_user_memory()` calls (curl probes, UI button) — out of phase 11 scope; track as a future observability item if needed.

Log line schema:

```
{"ts": "2026-05-22T22:39:34.123Z", "level": "info", "path": "memory",
 "agent_id": "chat", "team_id": null, "user_id": "7113965359",
 "db_id": "ultra-brain-main", "row_ids": ["..."], "latency_ms": 8421,
 "status": "ok", "extracted_count": 2}
```

On failure: `status: "error"`, `error_type: "ExceptionClassName"`, `error_msg: "<message>"`, `row_ids: []`.

## D-09 — Decision: HTTP timeout shape (11-02)

Replace the implicit `timeout=POLL_TIMEOUT + 5 = 35s` with an explicit `httpx.Timeout(connect=10, read=90, write=10, pool=90)`. Justification:

- `connect=10` — server is local (127.0.0.1); 10s is generous.
- `read=90` — accommodates chat (10 s typical) and supervisor (now fixed by 11-02, expected ≤30 s typical). Headroom for vault-query + reasoning chains.
- `write=10` — small form-encoded body; 10 s is generous.
- `pool=90` — Telegram polling loop reuses a single client; keep the pool wait > read budget.

`POLL_TIMEOUT=30` (the long-poll budget for Telegram getUpdates) stays as-is.

## D-10 — Verification protocol

After both 11-01 and 11-02 ship and deploy:

1. **Baseline snapshot** — `ai.agno_memories` row count + `pg_stat n_tup_ins/n_tup_upd`.
2. **Real Telegram message** — operator sends a memory-worthy message to the bot.
3. **5-second poll** — `GET /memories?user_id=<operator-telegram-id>` should return ≥1 new row.
4. **Log check** — `journalctl -u uab-brain.service` should show the OBS-01 structured log line with `status: "ok"` and the operator's `user_id`.
5. **Supervisor verification** — `curl -X POST http://127.0.0.1:7000/teams/supervisor/runs ...` returns HTTP 200 within 90 s.
6. **pg_stat delta** — `n_tup_ins` incremented by ≥1.

If any of (3)/(4)/(6) fails: open a fix-up plan; do not declare phase 11 done.

## D-11 — Threat model

| Threat | Mitigation |
|---|---|
| Memory-extraction LLM cost | `cheap-worker` model already configured; curator+ingest now opt-out; OBS-01 logs `latency_ms` so cost-per-run is visible. |
| PII / secrets in extracted memory | Out of phase 11 scope. Tracked separately (DIAG-BL or new MEM-04 candidate). |
| `user_id="default"` accumulation | Lint / startup assertion deferred to phase 15 (low priority — only one HTTP entry point that lacks `user_id` today: A2A and MCP). |
| Supervisor `reasoning=False` removes a feature | Operator confirms loss of structured CoT output is acceptable. The orchestrator model still produces thinking internally; we just stop trying to manual-CoT on top. |
| Raised httpx timeout (35s → 90s) could mask real backend issues | Acceptable: the underlying probe is the OBS-01 log + the smoke test. If supervisor regresses, the integration test catches it before timeout would matter. |
| Open AgentOS auth (DIAG-BL-09) lets anyone seed memory rows | Out of phase 11 scope. Track as backlog. |

## D-12 — What's NOT in phase 11

- Knowledge surface (phase 13).
- Eval harness (phase 12).
- Approvals (phase 14).
- worker.monitor polish (phase 15).
- Per-agent DB isolation (Option B; phase 10 rejected).
- AgentOS auth (DIAG-BL-09; phase 15 security).
- PII redaction (deferred).
- `user_id="default"` lint (deferred).

## D-13 — Rollback strategy

11-01 is purely additive (new file `instrumented_memory.py`, plus 1-arg additions to constructors). Rollback = revert the commit; previous behavior is restored. `InstrumentedMemoryManager` is a drop-in subclass; if it has a bug, swap back to `MemoryManager(...)` in `app.py`.

11-02 is a 2-line change. Rollback = revert. No data migration involved.

## D-14 — References

- `11-RESEARCH.md` — root research (read first).
- `evidence/experiment-2026-05-22.md` — controlled experiment that drove the scope reshape.
- `.planning/phases/10-diagnostic-audit/DB-ID-DECISION.md` — Option A locked.
- `.planning/phases/10-diagnostic-audit/AUDIT.md` — amended memory section.
- `.planning/phases/10-diagnostic-audit/BACKLOG.md` — DIAG-BL-01 (precondition) + DIAG-BL-04 (amended).
- Agno 2.6.7 source under `.venv/lib/python3.13/site-packages/agno/`.
