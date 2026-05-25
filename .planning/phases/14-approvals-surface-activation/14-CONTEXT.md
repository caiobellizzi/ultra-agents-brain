# Phase 14: Approvals Surface Activation - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning
**Source:** User delegated to agent recommendations after phase-specific gray area selection.

<domain>
## Phase Boundary

Surface Telegram-triggered Agno HITL approvals in the AgentOS Approvals UI and prove the same native approval row updates when the user taps Telegram Approve or Deny. This phase activates the existing `requires_confirmation=True` path; it does not add new gated tools, new channels, or a separate approval store.

**Deliverables:**
- A deterministic HITL smoke path that creates a pending row in `ai.agno_approvals` and `GET /approvals`.
- Telegram callback handling that updates the native AgentOS approval row state and continues the paused run.
- OBS-01 structured logging for approval creation, row resolution, and run-status update attempts.
- Verification evidence from DB/API/UI showing pending -> approved/rejected behavior and visible tool name/args.

**Out of scope:**
- New approval surfaces beyond AgentOS UI and Telegram.
- Per-agent DB isolation. Phase 10 locked shared `db_id="ultra-brain-main"` and approvals use `os_db`, not `?db_id=`.
- Sensitive argument redaction policy beyond using non-sensitive smoke inputs and truncating logs.
- Project-side mirror creation of approval rows if Agno native creation fails.

</domain>

<decisions>
## Implementation Decisions

### Canonical trigger path

- **D-01:** Use `/ingest /tmp/uab-approval-smoke.md` as the canonical phase smoke path. The operator/test harness creates that local fixture with harmless text before triggering the Telegram command. This avoids network flakiness from URL extraction while still exercising the real `ingest_to_vault` tool decorated with `@tool(requires_confirmation=True)`.
- **D-02:** The required evidence point is the paused response creating a native pending approval row before the user taps a button. Verification must capture `GET /approvals?run_id=<run_id>` and/or a `psql` row from `ai.agno_approvals` with `status='pending'`, `tool_name='ingest_to_vault'`, and the fixture path in `tool_args`.
- **D-03:** `/research <topic>` is optional secondary coverage, not a phase gate. Use it only if the planner wants to prove both existing gated tools still work after the core ingest path passes.

### State update contract

- **D-04:** Telegram is the required human resolution path. UI-side clicking is not a phase requirement; the UI is used to observe the row and final state.
- **D-05:** A Telegram callback must do two things: resolve the native AgentOS approval row and continue the paused run. The current adapter already posts `/agents/{agent_id}/runs/{run_id}/continue` with confirmed tool payloads. Phase 14 should add the missing row-state bridge if live/source verification confirms that continue alone leaves `ai.agno_approvals.status` as `pending`.
- **D-06:** Preferred bridge: look up the native approval by `run_id`, `approval_type='required'`, `status='pending'`, and matching `tool_call_id`; then call `POST /approvals/{approval_id}/resolve` with `status='approved'` or `status='rejected'`, `resolved_by='telegram:<user_id>'`, and minimal `resolution_data`. After that, call the existing `/runs/{run_id}/continue` endpoint with the full cached tool execution payload and `confirmed=true|false`.
- **D-07:** Verification must assert both fields because Agno distinguishes row resolution from run lifecycle: `status` should move `pending -> approved/rejected`, and `run_status` should move away from paused after continue. If Agno source/live behavior proves a different field is the UI's state source, document it in VERIFICATION.md and adjust the assertion, but do not weaken APPR-02 without evidence.
- **D-08:** Deny is first-class. The regression suite must cover both Approve and Deny callbacks: approve resolves `status='approved'` and attempts tool execution; deny resolves `status='rejected'` and continues/rejects the tool so the run does not remain paused.

### Tool argument visibility

- **D-09:** The approval row should expose Agno-native `tool_name` and `tool_args`; do not replace them with a project-side summary. APPR-03 is satisfied by proving the UI/API displays the underlying `ingest_to_vault` tool call and its arguments.
- **D-10:** Use non-sensitive fixture inputs for smoke tests. Do not introduce broad redaction in phase 14 because it could hide the exact action awaiting approval. Future redaction can wrap display/logging, but the native row remains the source of truth.
- **D-11:** OBS logs must avoid dumping full arbitrary args. Log `tool_name`, `tool_call_id`, `run_id`, `approval_id`, status transition, latency, and a truncated/safe arg summary.

### Broken native HITL fallback

- **D-12:** If a real `/ingest` run with `requires_confirmation=True` does not create a native row in `ai.agno_approvals`, stop and reopen the audit with secondary tag `RC-hitl-write-broken`. Do not build a project-side mirror writer for row creation; that would mask the exact Agno surface this phase is supposed to activate.
- **D-13:** Row-resolution bridging is allowed because APPR-02 specifically requires Telegram state changes to show in AgentOS. The bridge must update the native `ai.agno_approvals` row, not a new table.
- **D-14:** Verify the SqliteDb fallback behavior locally even though production uses Postgres. Phase 10 flagged DIAG-BL-02 as a risk; installed Agno source now shows Sqlite approval methods exist, but a unit/integration probe should confirm `/approvals` does not 503 with fallback DB.

### OBS-01 hook point and plan split

- **D-15:** Add an approval instrumentation helper, likely `agentos/approval_recorder.py` or `agentos/instrumented_approvals.py`, that wraps or patches approval DB methods on the shared `db` instance. The hook points are `create_approval`, `update_approval`, and `update_approval_run_status` because Agno's native approval code calls those methods internally.
- **D-16:** Keep logging failures non-fatal. Approval logging must never block a user approval or deny action. If the approval row update itself fails, do not continue the run silently; surface a Telegram error and let the user retry.
- **D-17:** Suggested plan split:
  - **14-01:** Instrument native approval DB methods, add local fallback probe, and add tests for creation/update log lines.
  - **14-02:** Add Telegram row-resolution bridge, preserve existing duplicate-tap guard, and test approve plus deny callback flows.
  - **14-03:** Run live verification on VPS: fixture ingest -> pending row -> Telegram approve/deny -> final row state -> UI evidence -> VERIFICATION.md.

### the agent's Discretion

- Exact module name for approval instrumentation.
- Whether the row-resolution bridge calls the HTTP approval API or a small internal helper, as long as it updates the native `ai.agno_approvals` row and remains testable.
- Exact OBS field ordering and log truncation length.
- Whether `/research` secondary coverage is included in 14-03 after the ingest path passes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap and requirements

- `.planning/ROADMAP.md` - Phase 14 goal and success criteria: pending row visible, Telegram state update within 2 seconds, tool name/args visible, structured approval logs.
- `.planning/REQUIREMENTS.md` - APPR-01, APPR-02, APPR-03, OBS-01 approval path.
- `.planning/PROJECT.md` - AgentOS is the single source of truth; Telegram is a dumb adapter; HITL gates live in Agno persistence.

### Phase 10 audit and DB decision

- `.planning/phases/10-diagnostic-audit/AUDIT.md` Section 4 - Approval surface root cause `RC-no-hitl-trigger-yet`, native table `ai.agno_approvals`, `GET /approvals` empty, and instruction to escalate to `RC-hitl-write-broken` if a real trigger still does not write a row.
- `.planning/phases/10-diagnostic-audit/DB-ID-DECISION.md` - Option A locked: one shared `PostgresDb(id="ultra-brain-main")`; approvals router uses AgentOS `os_db` only and ignores `db_id`.
- `.planning/phases/10-diagnostic-audit/BACKLOG.md` - DIAG-BL-02 fallback DB approval support risk and DIAG-BL-09 open AgentOS auth risk. Auth remediation is phase 15, but phase 14 should not make it harder.

### Prior surface patterns

- `.planning/phases/11-memory-surface-activation/11-CONTEXT.md` - Instrumented wrapper pattern, log-and-swallow OBS behavior, shared DB pin.
- `.planning/phases/12-evals-surface-activation/12-CONTEXT.md` - Post-run instrumentation pattern, suite/live split, OBS field discipline.
- `.planning/phases/13-knowledge-surface-activation/13-CONTEXT.md` - Native surface activation pattern: use existing Agno tables, do not create mirror storage, verify UI/API/DB together.

### Project code touch points

- `agentos/app.py` - Shared `db` construction and AgentOS `db=db` wiring. Approval instrumentation should patch/wrap this shared instance before agents handle runs.
- `agentos/tools/vault.py` - Existing `@tool(requires_confirmation=True)` tools: `ingest_to_vault` and `research_topic`.
- `channels/telegram_adapter.py` - Current approval button rendering, `_PAUSED_TOOLS` cache, callback validation, duplicate-tap guard, and `/runs/{run_id}/continue` call.
- `channels/SMOKE.md` - Existing HITL payload contract. Phase 14 may supersede its "do not call /approvals/{id}/resolve" note if row-state bridging is required for APPR-02.
- `tests/test_telegram_adapter.py` - Existing callback validation and duplicate-tap regression tests to extend.

### Agno source (read-only vendor reference)

- `.venv/lib/python3.13/site-packages/agno/run/approval.py` - `create_approval_from_pause`, `update_approval_run_status`, and approval dict fields.
- `.venv/lib/python3.13/site-packages/agno/os/routers/approvals/router.py` - `GET /approvals`, `POST /approvals/{approval_id}/resolve`, and `os_db`-only routing.
- `.venv/lib/python3.13/site-packages/agno/os/routers/agents/router.py` - `/agents/{agent_id}/runs/{run_id}/continue` behavior and dependency on pending approval resolution when auth is enabled.
- `.venv/lib/python3.13/site-packages/agno/os/auth.py` - `require_approval_resolved`, which blocks continuation with pending required approvals when authorization is enabled and caller lacks `approvals:write`.
- `.venv/lib/python3.13/site-packages/agno/agent/_tools.py` - `handle_tool_call_updates`; confirmed tools execute, denied tools are rejected.
- `.venv/lib/python3.13/site-packages/agno/agent/_run.py` - cleanup path updates approval `run_status` after run completion.
- `.venv/lib/python3.13/site-packages/agno/db/postgres/postgres.py` - `create_approval`, `get_approvals`, `update_approval`, `update_approval_run_status`.
- `.venv/lib/python3.13/site-packages/agno/db/sqlite/sqlite.py` - local fallback approval methods; verify DIAG-BL-02.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `channels/telegram_adapter.py::send_approval_buttons` already extracts `tool_call_id`, `tool_name`, and `tool_args` from paused requirements and stores cached tool executions in `_PAUSED_TOOLS`.
- `channels/telegram_adapter.py::handle_callback` already validates callback shape, agent id, UUID-shaped run id, and has a `_RESOLVED_RUNS` duplicate-tap guard.
- `agentos/app.py` already centralizes the shared DB object, making approval method instrumentation possible without changing every agent factory.
- Existing surface instrumentation (`agentos/instrumented_memory.py`, `agentos/eval_recorder.py`, `agentos/instrumented_knowledge.py`) provides the local style for OBS loggers and fault-injection tests.

### Established Patterns

- Surface activation phases use native Agno persistence tables as the source of truth. Do not create a parallel approval table.
- Instrumentation failures log and swallow; business-state failures do not. In this phase, failing to resolve the native approval row is business-state failure.
- Verification needs DB, API, and UI evidence together because os.agno.com has faithfully reflected backend emptiness in earlier audits.
- Shared `db_id="ultra-brain-main"` is locked. Approval endpoints do not use `db_id` at all.

### Integration Points

- Pending row creation: Agno internals call `db.create_approval()` when a run pauses for a required confirmation.
- Row lookup: `GET /approvals?run_id=<run_id>&status=pending&approval_type=required` can identify the row for Telegram callback resolution; matching `tool_call_id` should be used when multiple requirements exist.
- Row resolution: `POST /approvals/{approval_id}/resolve` updates `status`, `resolved_by`, `resolved_at`, and optional `resolution_data`.
- Run continuation: existing adapter call to `/agents/{agent_id}/runs/{run_id}/continue` or `/teams/{team_id}/runs/{run_id}/continue` still resumes tool execution/rejection.
- UI evidence: `GET /approvals` and os.agno.com Approvals tab should show the same row fields.

</code_context>

<specifics>
## Specific Ideas

- Canonical smoke fixture: create `/tmp/uab-approval-smoke.md` with harmless content, then send `/ingest /tmp/uab-approval-smoke.md` through Telegram.
- Required row evidence: `tool_name='ingest_to_vault'`; `tool_args.source` points at the fixture; `status` starts as `pending`; `run_status` starts as paused.
- Required state evidence: Approve ends at `status='approved'`; Deny ends at `status='rejected'`; `run_status` should no longer be paused after callback handling.
- OBS approval log schema should include at least `ts`, `level`, `path='approval'`, `op='create|resolve|run_status'`, `agent_id`, `user_id`, `run_id`, `approval_id`, `tool_call_id`, `tool_name`, `status_from`, `status_to`, `run_status`, `latency_ms`, and `status='ok|error'`.

</specifics>

<verification_protocol>
## Verification Protocol

After plans 14-01 through 14-03 ship and deploy:

1. **Fixture setup:** On the VPS, create `/tmp/uab-approval-smoke.md` with harmless text. Confirm the Telegram adapter and AgentOS point at the same AgentOS base URL.
2. **Pending row creation (APPR-01):** Send `/ingest /tmp/uab-approval-smoke.md` in Telegram. Before tapping any button, `GET /approvals?run_id=<run_id>` returns one pending row with `tool_name='ingest_to_vault'` and matching `tool_args`.
3. **UI pending check (APPR-01/APPR-03):** os.agno.com Approvals tab shows the pending row and displays the tool name plus arguments.
4. **Approve path (APPR-02):** Tap Approve. Within 2 seconds, API/DB shows `status='approved'`, `resolved_by` populated with Telegram user identity, and `run_status` no longer paused. Telegram receives the tool result or a clear completed message.
5. **Deny path (APPR-02):** Repeat with a second fixture/run and tap Deny. Within 2 seconds, API/DB shows `status='rejected'`, `resolved_by` populated, and the run does not remain paused.
6. **OBS-01 log check:** `journalctl -u uab-brain.service` (or local test log capture) shows `path='approval'` entries for create, resolve, and run_status paths, with at least one fault-injection error covered by unit tests.
7. **Fallback DB check:** With `POSTGRES_DSN_SESSIONS` unset locally, `/approvals` does not 503 and the local fallback test documents actual Sqlite behavior.

If a real gated run does not create a native approval row, stop and reopen the audit as `RC-hitl-write-broken`.

</verification_protocol>

<threat_model>
## Threat Model

| Threat | Mitigation |
|---|---|
| Continue endpoint executes the tool but leaves approval row pending | D-05/D-06 bridge native row resolution before continue; tests assert final status. |
| Row resolved but run continuation fails | Surface Telegram error, log `status='error'`, and allow retry; do not silently claim success. |
| Duplicate button taps double-resolve or double-continue | Preserve `_RESOLVED_RUNS` guard; add tests that resolve and continue each happen once. |
| Multiple pending requirements on one run resolve the wrong row | Match by `run_id` and `tool_call_id`, not only latest pending row. |
| Full tool args leak sensitive data into logs | Keep native DB args for UI truth, but log only truncated/safe summaries; use non-sensitive smoke inputs. |
| Agno native creation path broken | Stop and reopen audit; no mirror row creation. |
| Future AgentOS auth blocks Telegram continue with pending approval | Resolving the row before continue aligns with `require_approval_resolved`. Phase 15 auth work should not break this path. |

</threat_model>

<deferred>
## Deferred Ideas

- Sensitive approval argument redaction policy across DB rows, UI display, and logs. This should be designed once, not patched only for ingest.
- UI-side approval resolution as an operator workflow. Phase 14 only requires Telegram as the human path and UI as the evidence surface.
- Additional gated-tool coverage for `/research <topic>` if the operator wants broader HITL assurance after the ingest path passes.
- AgentOS auth hardening remains phase 15 / security backlog territory; do not solve it inside approval activation.

</deferred>

<rollback>
## Rollback Strategy

- Approval instrumentation is additive. Roll back by removing the approval method patch/wrapper and the OBS log lines stop; native Agno approval behavior remains.
- Telegram bridge changes are localized to `channels/telegram_adapter.py`. Roll back by reverting the bridge helper and callback flow; existing continue-only behavior is restored.
- Live verification docs are planning artifacts only and need no runtime rollback.
- Approval DB rows created during smoke tests are disposable operational evidence. If needed, delete only the smoke rows by `run_id`/fixture args after verification, not with broad table truncation.

</rollback>

---

*Phase: 14-Approvals Surface Activation*
*Context gathered: 2026-05-25*
