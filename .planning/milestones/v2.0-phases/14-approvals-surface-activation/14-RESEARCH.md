# Phase 14: Approvals Surface Activation — Research

**Researched:** 2026-05-27
**Domain:** Agno native HITL approval persistence, Telegram callback bridge, OBS-01 structured logging
**Confidence:** HIGH — all findings sourced directly from Agno 2.6.7 venv source and project codebase
**Agno version:** 2.6.7 (`.venv/lib/python3.13/site-packages/agno-2.6.7.dist-info/METADATA`)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use `/ingest /tmp/uab-approval-smoke.md` as the canonical smoke path.
- **D-02:** Required evidence: `GET /approvals?run_id=<run_id>` shows pending row with `tool_name='ingest_to_vault'` and fixture path in `tool_args`, captured before any button tap.
- **D-03:** `/research <topic>` is optional secondary coverage, not a phase gate.
- **D-04:** Telegram is the required human resolution path. UI is evidence-only.
- **D-05:** Telegram callback must do two things: resolve native AgentOS approval row AND continue the paused run.
- **D-06:** Preferred bridge: look up approval by `run_id + approval_type='required' + status='pending' + matching tool_call_id`, then `POST /approvals/{approval_id}/resolve`, then existing `/runs/{run_id}/continue`.
- **D-07:** Verify both `status` (row state) and `run_status` (run lifecycle) after each callback.
- **D-08:** Deny is first-class — must cover approve AND deny in regression suite.
- **D-09:** Expose Agno-native `tool_name` and `tool_args`. Do not replace with project-side summary.
- **D-10:** Non-sensitive fixture inputs for smoke. No broad redaction in phase 14.
- **D-11:** OBS logs truncate args, include: `tool_name`, `tool_call_id`, `run_id`, `approval_id`, status transition, latency, truncated arg summary.
- **D-12:** If native row creation fails, stop and reopen audit as `RC-hitl-write-broken`. No project-side mirror.
- **D-13:** Row-resolution bridging is allowed. Bridge must update native `ai.agno_approvals`.
- **D-14:** Verify SqliteDb fallback behavior for `/approvals` locally (DIAG-BL-02 risk).
- **D-15:** Approval instrumentation via `agentos/approval_recorder.py` (or similar), wrapping/patching `create_approval`, `update_approval`, `update_approval_run_status` on the shared `db` instance.
- **D-16:** Logging failures are non-fatal. Row-resolution failures ARE fatal (surface Telegram error, allow retry).
- **D-17:** Plan split: 14-01 (DB instrumentation + Sqlite probe + tests), 14-02 (Telegram bridge + tests), 14-03 (VPS live verification).

### Claude's Discretion

- Exact module name for approval instrumentation.
- Whether bridge calls HTTP approval API or small internal helper (as long as it updates native `ai.agno_approvals` and is testable).
- Exact OBS field ordering and log truncation length.
- Whether `/research` secondary coverage is included in 14-03.

### Deferred Ideas (OUT OF SCOPE)

- Sensitive approval argument redaction policy.
- UI-side approval resolution.
- Additional gated-tool coverage for `/research <topic>` (unless ingest path passes and time allows).
- AgentOS auth hardening (phase 15 territory).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APPR-01 | HITL approval events created via Telegram inline buttons appear in AgentOS approvals UI list | Row creation confirmed via `create_approval_from_pause` in `agno/run/approval.py:176`. Instrumentation hook in `create_approval`. |
| APPR-02 | Approving/rejecting via Telegram updates approval row state (pending → approved/rejected) within 2 seconds | `POST /approvals/{approval_id}/resolve` confirmed in `agno/os/routers/approvals/router.py:147`. Bridge pattern: GET row by `run_id`, then POST resolve. |
| APPR-03 | Approvals UI displays the underlying tool call and arguments awaiting approval | Native `tool_name` and `tool_args` fields on the approval row confirmed. `_build_approval_dict` extracts from `run_response.tools`. |
| OBS-01 (approval path) | Approval write path emits structured log on creation and on state change | Three hook points confirmed: `create_approval`, `update_approval`, `update_approval_run_status`. Pattern mirrors memory/eval/knowledge surfaces. |
</phase_requirements>

---

## Summary

Phase 14 activates the existing `@tool(requires_confirmation=True)` HITL path in Agno 2.6.7 and bridges Telegram approval decisions to the native `ai.agno_approvals` table. The core mechanics are already present in the venv source — no monkey-patching of internals is needed. Row creation happens automatically inside Agno's `handle_agent_run_paused` via `create_approval_from_pause(db=agent.db, ...)`. The DB methods (`create_approval`, `update_approval`, `update_approval_run_status`) are synchronous methods on `PostgresDb` and `SqliteDb` — both backends fully implement all approval methods, so DIAG-BL-02 risk is LOW.

The critical gap is the Telegram-side bridge. The current `handle_callback` in `channels/telegram_adapter.py` calls `/runs/{run_id}/continue` directly without first resolving the approval row. Agno's `check_and_apply_approval_resolution` in `_run.py` reads the approval row during continue processing, so if `status` is still `pending`, the run gate would normally error — but since auth/authorization is likely disabled on the local AgentOS instance, continue may succeed while leaving the row pending (APPR-02 gap). The bridge must call `POST /approvals/{approval_id}/resolve` before `/continue`.

OBS-01 instrumentation follows the exact pattern established by `agentos/instrumented_memory.py` and `agentos/eval_recorder.py`: a module-level `log = logging.getLogger("agentos.approval")`, a wrapper/patcher that intercepts `db.create_approval`, `db.update_approval`, and `db.update_approval_run_status`, and a `_emit()` method that writes a JSON-serialized structured log line. No external packages are needed.

**Primary recommendation:** Implement `agentos/approval_recorder.py` as a DB-method wrapper (not subclass) that patches the three approval methods on the shared `db` instance in `agentos/app.py`. In `channels/telegram_adapter.py`, add a `_resolve_approval_row(client, run_id, tool_call_id, status)` async helper that calls `GET /approvals?run_id=...&status=pending&approval_type=required`, matches by `tool_call_id`, then POSTs `/approvals/{id}/resolve` before the existing `/continue` call.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Approval row creation | API/Backend (Agno internals) | — | `create_approval_from_pause` is called inside `handle_agent_run_paused` in `agno/agent/_run.py`. No project code triggers it; it fires automatically when a run pauses. |
| Approval row resolution | API/Backend (Telegram adapter → AgentOS HTTP) | — | Adapter calls `POST /approvals/{id}/resolve` against AgentOS, which calls `db.update_approval`. |
| Run continuation after resolve | API/Backend (Telegram adapter → AgentOS HTTP) | — | Existing `/agents/{id}/runs/{run_id}/continue` call; order matters: resolve first, then continue. |
| OBS-01 approval logging | API/Backend (approval_recorder wrapper) | — | Patches shared `db` instance in `agentos/app.py` at startup, exactly like `patch_classes_for_recording`. |
| Approval row visibility | AgentOS UI (os.agno.com) | — | Approval rows in `ai.agno_approvals` are surfaced by `GET /approvals`. UI is evidence-only. |
| Sqlite fallback probe | Local dev environment | — | DIAG-BL-02: probe `GET /approvals` with `POSTGRES_DSN_SESSIONS` unset. |

---

## Standard Stack

This phase installs **no new packages**. All capabilities are available in the current venv.

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| agno | 2.6.7 | Approval persistence, `/approvals` router, `_run.py` pause hooks | Native platform library |
| httpx | (project dep) | Async HTTP for Telegram bridge calling `/approvals/{id}/resolve` | Already used in telegram_adapter.py |
| pytest | (project dep) | TDD test harness | Project-standard test framework |
| unittest.mock | stdlib | Mock `db` methods and HTTP client in unit tests | Matches existing test_telegram_adapter.py pattern |

### No New Packages Required
All approval DB methods, the `/approvals` router, and the `approval.py` helpers are in the installed agno 2.6.7 venv.

---

## Package Legitimacy Audit

No new packages are installed in this phase. Section is not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
Telegram user
     |
     | /ingest /tmp/uab-approval-smoke.md
     v
channels/telegram_adapter.py
  route_message()
     |
     | POST /agents/ingest/runs
     v
AgentOS (agentos/app.py)
  ingest_agent runs → hits @tool(requires_confirmation=True)
     |
     | [Agno internals: handle_agent_run_paused()]
     |   └─ create_approval_from_pause(db=db, ...)   ← HOOK POINT 1
     |       └─ db.create_approval(approval_data)    ← patched by approval_recorder
     |           └─ OBS log: path='approval', op='create'
     |
     | RunStatus.paused → PAUSED response with requirements[]
     v
telegram_adapter.py
  send_approval_buttons()  → caches tools in _PAUSED_TOOLS[run_id]
     |
     | User taps Approve/Deny
     v
handle_callback()
  1. _resolve_approval_row(client, run_id, tool_call_id, status)   ← NEW BRIDGE
     |  GET /approvals?run_id=...&status=pending&approval_type=required
     |  match by tool_call_id
     |  POST /approvals/{approval_id}/resolve {status, resolved_by, resolution_data}
     |      └─ db.update_approval(...)               ← HOOK POINT 2 (patched)
     |          └─ OBS log: path='approval', op='resolve'
     v
  2. POST /agents/ingest/runs/{run_id}/continue  (existing)
     |
     | Agno internals: check_and_apply_approval_resolution → runs confirmed tool
     | cleanup: update_approval_run_status()             ← HOOK POINT 3 (patched)
     |     └─ OBS log: path='approval', op='run_status'
     v
  Tool result / denial response → send_message() to Telegram
```

### Recommended Project Structure

```
agentos/
├── approval_recorder.py      # NEW — DB-method wrapper + OBS-01 logger
channels/
├── telegram_adapter.py       # MODIFIED — add _resolve_approval_row() helper
tests/
├── test_telegram_adapter.py  # MODIFIED — add approve/deny bridge tests
├── test_approval_recorder.py # NEW — instrumentation + fault-injection tests
```

### Pattern 1: DB Method Wrapping (approval_recorder.py)

This phase uses a **wrapping approach** — not subclassing, not monkey-patching at class level — because the three methods (`create_approval`, `update_approval`, `update_approval_run_status`) live on the shared `db` instance constructed in `agentos/app.py`.

The established precedent is `eval_recorder.py::patch_classes_for_recording` for class-level patches. For approval recording, the `db` instance is the right surface because:
1. Approvals are `db`-level, not agent-level.
2. The `db` is passed to every agent; patching it once covers all code paths.
3. Wrapping instance methods avoids touching Agno internals.

**Example (mirrors eval_recorder pattern):**
```python
# Source: agentos/eval_recorder.py pattern + agno/run/approval.py hook points
def patch_db_for_approval_recording(db: Any) -> None:
    """Wrap create_approval, update_approval, update_approval_run_status on db instance."""
    if getattr(db, "_approval_recorder_patched", False):
        return

    original_create = db.create_approval
    original_update = db.update_approval
    original_run_status = db.update_approval_run_status

    def instrumented_create(approval_data):
        started = time.monotonic()
        try:
            result = original_create(approval_data)
            _emit_approval(
                op="create", approval_id=approval_data.get("id"),
                run_id=approval_data.get("run_id"), tool_name=approval_data.get("tool_name"),
                tool_call_id=None, status_from=None, status_to="pending",
                agent_id=approval_data.get("agent_id"), user_id=approval_data.get("user_id"),
                latency_ms=int((time.monotonic()-started)*1000), status="ok",
                tool_args_summary=_truncate_args(approval_data.get("tool_args")),
            )
            return result
        except Exception as exc:
            _emit_approval(op="create", ..., status="error", error_type=..., error_msg=...)
            raise

    db.create_approval = instrumented_create
    db.update_approval = instrumented_update
    db.update_approval_run_status = instrumented_run_status
    db._approval_recorder_patched = True
```

Call `patch_db_for_approval_recording(db=db)` in `agentos/app.py` after the `db` is constructed, before agents are initialized.

### Pattern 2: Telegram Bridge — resolve before continue

The current `handle_callback` flow:
```
1. TOCTOU guard → _RESOLVED_RUNS.add(run_id)
2. Build tools_list (existing)
3. POST /agents/{id}/runs/{run_id}/continue  ← row stays pending
```

Required flow for APPR-02:
```
1. TOCTOU guard → _RESOLVED_RUNS.add(run_id)
2. Build tools_list (existing, unchanged)
3. _resolve_approval_row(client, run_id, agent_id, tool_call_id, action)  ← NEW
   a. GET /approvals?run_id={run_id}&status=pending&approval_type=required
   b. find entry where tool_call_id matches (or take first if single)
   c. POST /approvals/{approval_id}/resolve
      body: {status: "approved"|"rejected", resolved_by: "telegram:{tg_user_id}"}
   d. if resolution fails: log error, send Telegram error, _RESOLVED_RUNS.discard(run_id), return
4. POST /agents/{id}/runs/{run_id}/continue  ← existing code, unchanged
```

**Key implementation note:** `GET /approvals` is a `GET` endpoint that returns `PaginatedResponse[ApprovalResponse]`. The adapter must parse `response.data[]` and match by `tool_call_id`. When there's a single paused tool (smoke path), `data[0]` is sufficient. For multi-tool runs, match by `tool_call_id` from the cached tools.

**`POST /approvals/{approval_id}/resolve` body schema** (from `agno/os/routers/approvals/schema.py` implied by router source):
```json
{
  "status": "approved",          // or "rejected"
  "resolved_by": "telegram:123456789",
  "resolution_data": null        // optional, not needed for confirmation tools
}
```

The router's `resolve_approval` handler writes `status`, `resolved_by`, `resolved_at`, and optional `resolution_data` via `db.update_approval(approval_id, expected_status="pending", ...)`. The `expected_status="pending"` guard means double-resolves return `None` → 409 (conflict). The bridge must handle 409 gracefully (same as the existing 409 guard on `/continue`).

### Pattern 3: OBS-01 Log Structure

Based on the established patterns in `agentos/instrumented_memory.py` and `agentos/eval_recorder.py`, the approval log schema:

```python
# Source: agentos/instrumented_memory.py:192-220 pattern
record = {
    "path": "approval",         # surface identifier (mirrors "memory", "eval", "knowledge")
    "op": "create",             # "create" | "resolve" | "run_status"
    "agent_id": agent_id,       # from approval_data or context
    "user_id": user_id,
    "db_id": db_id,             # getattr(db, "id", None)
    "run_id": run_id,
    "approval_id": approval_id,
    "tool_call_id": tool_call_id,
    "tool_name": tool_name,
    "tool_args_summary": ...,   # truncated, max ~100 chars
    "status_from": "pending",   # None for op="create"
    "status_to": "approved",    # "pending" for op="create", actual for op="resolve"
    "run_status": run_status,   # only for op="run_status"
    "latency_ms": latency_ms,
    "status": "ok",             # "ok" | "error"
    # error fields — only on status="error":
    "error_type": error_type,
    "error_msg": error_msg[:200],
}
# Success: log.info("OBS-01 approval write: %s", json.dumps(record, default=str))
# Failure: log.error("OBS-01 approval write failed: %s", json.dumps(record, default=str))
```

Logger: `log = logging.getLogger("agentos.approval")` with the same `log.setLevel(logging.INFO)` + StreamHandler boilerplate as sibling modules.

### Anti-Patterns to Avoid

- **Patching Agno internals directly (`agno/run/approval.py`):** These are vendor files in the venv. Patch the `db` instance instead.
- **Building a mirror approval table:** D-12 explicitly forbids this. If native creation fails, stop and audit.
- **Resolving by latest pending row without matching `tool_call_id`:** When multiple tools require confirmation on one run (possible in future), matching only "latest pending" would resolve the wrong row.
- **Calling `/continue` before `/resolve`:** If auth is later enabled, `require_approval_resolved` in `agno/os/auth.py` will block continuation when status is still `pending`. Always resolve first.
- **Making log failures fatal:** OBS-01 logging must never block a user approval decision (D-16).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Approval row creation | Custom DB writer in project | Agno's `create_approval_from_pause()` already does this automatically when run pauses | Wiring is already in `handle_agent_run_paused` in `agno/agent/_run.py` |
| Approval row resolution HTTP endpoint | Custom FastAPI route | Agno's `POST /approvals/{approval_id}/resolve` in `agno/os/routers/approvals/router.py` | Already wired to `AgentOS` instance |
| Approval row lookup | Raw SQL against `ai.agno_approvals` | `GET /approvals?run_id=...&status=pending&approval_type=required` HTTP endpoint | Router handles auth, pagination, and schema |
| Tool execution gating on continue | Custom confirm/deny flag | Agno's `check_and_apply_approval_resolution` already applied in `_run.py:2973` | Reads approval row, sets `confirmed` on tool executions |
| Structured log emission | Custom log format | Mirror `_emit()` pattern from `instrumented_memory.py` | Consistent OBS-01 schema across all surfaces |

**Key insight:** Agno 2.6.7 has all HITL plumbing already. The work is (1) proving it fires with a real run, (2) bridging the Telegram callback to call `/resolve` before `/continue`, and (3) wrapping the three `db` methods for OBS-01 logging.

---

## Runtime State Inventory

> Phase 14 is not a rename/refactor phase. Section omitted.

---

## Common Pitfalls

### Pitfall 1: `check_and_apply_approval_resolution` blocks `/continue` with pending row

**What goes wrong:** The continue endpoint calls `check_and_apply_approval_resolution` (or its async variant) in `agno/agent/_run.py:2973`. If the approval row is still `pending`, it raises `RuntimeError("Approval is still pending")`. The run never resumes. With auth disabled (current state), this check is technically skipped by `require_approval_resolved` dependency — but the in-process `check_and_apply_approval_resolution` call inside the agent run still executes.

**Why it happens:** The bridge calls `/continue` before resolving the row.

**How to avoid:** Always call `POST /approvals/{approval_id}/resolve` and confirm HTTP 200 before calling `/continue`. The bridge helper `_resolve_approval_row` must be awaited and must return early with a Telegram error message if resolve fails.

**Warning signs:** `/continue` returns 500 with "Approval is still pending" or "No approval record found".

### Pitfall 2: `tool_call_id` in `_PAUSED_TOOLS` cache vs. approval row

**What goes wrong:** The `tool_call_id` stored in `_PAUSED_TOOLS` (from `requirements[].tool_execution.tool_call_id`) must match what `GET /approvals` returns in `approval.tool_call_id` (or inside `requirements[]` JSON). If these differ, the bridge looks up the wrong row.

**Why it happens:** Agno's `_build_approval_dict` extracts `tool_call_id` from `first_tool`. If multiple requirements exist, it takes the first one's `tool_call_id`. The Telegram adapter stores all cached tools but sends the clicked tool's `tool_call_id` in `callback_data`.

**How to avoid:** In the bridge, fetch all pending approvals for the run and match by `tool_call_id`. For the smoke path (single tool), this is trivially the first and only row.

**Warning signs:** Bridge returns "no matching approval found" despite a pending row existing.

### Pitfall 3: `_RESOLVED_RUNS` guard released on failed resolve — must handle new failure modes

**What goes wrong:** Currently, `_RESOLVED_RUNS.discard(run_id)` is only called on non-409 `/continue` failure. With the new bridge, a resolve failure also needs to release the marker so the user can retry.

**Why it happens:** The TOCTOU guard marks run_id before the HTTP calls. If the bridge fails, the run_id stays in `_RESOLVED_RUNS` and subsequent taps are silently dropped.

**How to avoid:** In `_resolve_approval_row`, if any HTTP call fails in a non-idempotent way (not 409), call `_RESOLVED_RUNS.discard(run_id)` before returning.

**Warning signs:** User taps Approve, sees error message, taps again, nothing happens.

### Pitfall 4: `POST /approvals/{id}/resolve` returns 404 under user_isolation

**What goes wrong:** The router's `resolve_approval` handler has this guard:
```python
if get_scoped_user_id(request) is not None:
    raise HTTPException(status_code=404, detail="Approval not found")
```
Under `AuthorizationConfig(user_isolation=True)`, non-admin callers get 404 even when the approval exists.

**Why it happens:** The approval's `user_id` is the run initiator. The Telegram adapter is a server-side caller without a JWT — so it calls AgentOS without auth headers. With auth disabled (current production state), this is not triggered. But Phase 15 auth work could activate it.

**How to avoid:** Document this interaction in VERIFICATION.md. For Phase 14, auth is disabled; the bridge works as-is. Phase 15 must ensure the Telegram adapter's AgentOS calls either use an admin token or that `user_isolation` is not enabled for the approval resolve path.

**Warning signs:** Bridge resolve returns 404 on a row that definitely exists.

### Pitfall 5: SqliteDb `update_approval` returns `None` (DIAG-BL-02)

**What goes wrong:** SqliteDb's `update_approval` returns `None` if `rowcount == 0` (no row matched or expected_status mismatch). The HTTP layer maps this to 409. But the test probe should also verify that `GET /approvals` does not 503 with `SqliteDb`.

**Why it happens:** DIAG-BL-02 flagged this as a risk. The sqlite approval methods ARE implemented (verified by grep in `sqlite.py:4661`), so 503 should not occur.

**How to avoid:** D-14 requires a unit test with the sqlite fallback. Write a test that constructs `SqliteDb`, calls `create_approval` + `get_approvals` + `update_approval`, and confirms no 503 and correct behavior.

**Warning signs:** `GET /approvals` returns 503 when `POSTGRES_DSN_SESSIONS` is unset.

---

## Code Examples

### Approval row fields written by `create_approval_from_pause`
```python
# Source: agno/run/approval.py - _build_approval_dict()
approval_data = {
    "id": str(uuid4()),                          # approval_id
    "run_id": run_response.run_id,
    "session_id": run_response.session_id or "",
    "status": "pending",                         # always "pending" at creation
    "approval_type": "required",                 # for @tool(requires_confirmation=True)
    "pause_type": "confirmation",                # derived from tool flags
    "tool_name": first_tool.tool_name,           # "ingest_to_vault"
    "tool_args": first_tool.tool_args,           # {"source": "/tmp/uab-approval-smoke.md"}
    "source_type": "agent",
    "agent_id": agent_id,
    "user_id": user_id,
    "source_name": agent_name,
    "requirements": [...],                       # serialized requirements
    "context": {"tool_names": ["ingest_to_vault"]},
    "resolved_by": None,
    "resolved_at": None,
    "created_at": now_epoch_s(),
    "run_status": RunStatus.paused.value,        # "paused"
}
```

### Bridge: resolve approval before continue
```python
# Source: agno/os/routers/approvals/router.py:147 (resolve endpoint)
# and existing handle_callback pattern in channels/telegram_adapter.py

async def _resolve_approval_row(
    client: httpx.AsyncClient,
    run_id: str,
    tool_call_id: str,
    action: str,  # "approve" or "deny"
    tg_user_id: int,
    agent_id: str,
    chat_id: int,
) -> Optional[str]:
    """Resolve the native AgentOS approval row. Returns approval_id or None on failure."""
    # Step 1: find the pending approval for this run
    approvals_url = f"{AGENTOS_BASE_URL}/approvals"
    params = {"run_id": run_id, "status": "pending", "approval_type": "required"}
    r = await client.get(approvals_url, params=params)
    if r.status_code != 200:
        return None
    data = r.json().get("data", [])
    # Match by tool_call_id when possible (multi-tool safety)
    approval = next(
        (a for a in data if a.get("tool_call_id") == tool_call_id),
        data[0] if data else None,
    )
    if not approval:
        return None
    approval_id = approval["id"]

    # Step 2: resolve
    resolve_url = f"{AGENTOS_BASE_URL}/approvals/{approval_id}/resolve"
    resolve_body = {
        "status": "approved" if action == "approve" else "rejected",
        "resolved_by": f"telegram:{tg_user_id}",
    }
    r2 = await client.post(resolve_url, json=resolve_body)
    if r2.status_code == 409:
        # Already resolved (duplicate callback won the race) — treat as success
        return approval_id
    if r2.status_code not in (200, 201):
        return None  # caller must surface error
    return approval_id
```

### `update_approval` signature (for instrumentation wrapper)
```python
# Source: agno/db/postgres/postgres.py:4905 and agno/db/sqlite/sqlite.py:4753
def update_approval(
    self,
    approval_id: str,
    expected_status: Optional[str] = None,  # "pending" enforces CAS semantics
    **kwargs: Any                             # status, resolved_by, resolved_at, resolution_data
) -> Optional[Dict[str, Any]]:
    # Returns None if no row matched or expected_status mismatch (→ 409 from router)
    # Returns updated approval dict on success
```

### `update_approval_run_status` signature
```python
# Source: agno/run/approval.py:update_approval_run_status() + agno/db/postgres/postgres.py:4951
def update_approval_run_status(self, run_id: str, run_status: RunStatus) -> int:
    # Returns count of rows updated (0 or more)
    # Called in agno/agent/_run.py:4854 during run cleanup after continuation
```

### SqliteDb approval methods (DIAG-BL-02 verification)
```python
# Source: agno/db/sqlite/sqlite.py:4661 — full set of 7 approval methods implemented
# No NotImplementedError raised. All methods return expected types.
# GET /approvals will NOT 503 with SqliteDb — the router calls _db_call("get_approvals", ...)
# which checks for NotImplementedError; since SqliteDb implements it, 200 is returned.
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No HITL path active | `@tool(requires_confirmation=True)` already decorated on `ingest_to_vault` and `research_topic` in `agentos/tools/vault.py` | Agno 2.6.x + project phase setup | Trigger exists; row creation will fire on first real run |
| Manual approval via UI | Telegram inline buttons (existing), plus native row resolution (new in phase 14) | Phase 14 bridges these | Row state update joins run continuation |
| Telegram /continue only | /resolve + /continue sequence | Phase 14 (D-05, D-06) | APPR-02 closes |

**Not deprecated but requires attention:**
- `channels/SMOKE.md` has a note "do not call /approvals/{id}/resolve" — this note is superseded by D-13 and should be updated in 14-02.

---

## Open Questions

1. **Does `ai.agno_approvals` have a `tool_call_id` column or is it nested inside `requirements[]` JSON?**
   - What we know: The Phase 10 audit schema shows `tool_call_id character varying` as a top-level column. `_build_approval_dict` in `agno/run/approval.py` sets `tool_name` and `tool_args` from `first_tool` but the approval dict does NOT include `tool_call_id` as a top-level field — it's inside `requirements[]` serialized JSON.
   - What's unclear: The bridge matching by `tool_call_id` from `GET /approvals` response — does `ApprovalResponse` schema include it directly or must we parse `requirements[]`?
   - Recommendation: In 14-01, run a real smoke trigger and `psql \d ai.agno_approvals` to confirm column presence. If `tool_call_id` is not top-level, match on `data[0]` for single-tool smoke path, and add `requirements` JSON parsing for multi-tool future case.

2. **Does `/runs/{run_id}/continue` always call `check_and_apply_approval_resolution` before executing the tool?**
   - What we know: `_run.py:2973` shows `check_and_apply_approval_resolution(agent.db, run_id, run_response)` is called. This reads the approval row and applies `confirmed` status to tools.
   - What's unclear: Is this called in ALL continue paths (non-stream, stream, team vs. agent)?
   - Recommendation: For Phase 14 smoke path (non-stream, agent), line 2973 confirms it. Resolve first to ensure the status is `approved`/`rejected` before continue reads it.

3. **`GET /approvals` auth behavior with `user_id` scoping**
   - What we know: The router applies `get_scoped_user_id(request)` to filter by `user_id`. With auth disabled (no JWT), `get_scoped_user_id` returns `None` → no filter applied → all approvals visible.
   - What's unclear: When Phase 15 enables auth, will the adapter's calls to `/approvals` and `/approvals/{id}/resolve` need bearer tokens?
   - Recommendation: Document in VERIFICATION.md that Phase 15 must not break this path. Phase 14 does not need to solve it.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| agno (venv) | All approval internals | ✓ | 2.6.7 | — |
| PostgreSQL (VPS) | 14-03 live verification | ✓ | production VPS | SqliteDb locally |
| SqliteDb | DIAG-BL-02 probe (14-01) | ✓ | stdlib sqlite | — |
| httpx | Telegram bridge HTTP calls | ✓ | project dep | — |
| pytest | TDD test suite | ✓ | project dep | — |

No missing dependencies. Phase 14 is entirely in-process Python + existing HTTP endpoints.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (project standard) |
| Config file | `pytest.ini` or `pyproject.toml` (check project root) |
| Quick run command | `pytest tests/test_approval_recorder.py tests/test_telegram_adapter.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| APPR-01 | `create_approval` called when run pauses | unit | `pytest tests/test_approval_recorder.py::test_create_approval_logs_ok -x` | ❌ Wave 0 (14-01) |
| APPR-01 | OBS log emitted on approval creation | unit | `pytest tests/test_approval_recorder.py::test_obs_log_on_create -x` | ❌ Wave 0 (14-01) |
| APPR-01 | `GET /approvals` returns pending row after smoke trigger | integration (14-03, VPS) | manual — `curl` | n/a |
| APPR-02 | Telegram Approve callback calls `/approvals/{id}/resolve` then `/continue` | unit | `pytest tests/test_telegram_adapter.py::TestApprovalBridge::test_approve_resolves_then_continues -x` | ❌ Wave 0 (14-02) |
| APPR-02 | Telegram Deny callback calls `/approvals/{id}/resolve` with status=rejected | unit | `pytest tests/test_telegram_adapter.py::TestApprovalBridge::test_deny_resolves_rejected -x` | ❌ Wave 0 (14-02) |
| APPR-02 | Resolve failure triggers Telegram error, releases _RESOLVED_RUNS marker | unit | `pytest tests/test_telegram_adapter.py::TestApprovalBridge::test_resolve_failure_releases_guard -x` | ❌ Wave 0 (14-02) |
| APPR-02 | 409 on resolve is treated as idempotent success (already resolved) | unit | `pytest tests/test_telegram_adapter.py::TestApprovalBridge::test_resolve_409_is_ok -x` | ❌ Wave 0 (14-02) |
| APPR-03 | `tool_name` and `tool_args` visible in approval row | unit | `pytest tests/test_approval_recorder.py::test_tool_name_in_approval_data -x` | ❌ Wave 0 (14-01) |
| OBS-01 | `update_approval` emits resolve OBS log | unit | `pytest tests/test_approval_recorder.py::test_update_approval_logs_resolve -x` | ❌ Wave 0 (14-01) |
| OBS-01 | `update_approval_run_status` emits run_status OBS log | unit | `pytest tests/test_approval_recorder.py::test_update_run_status_logs -x` | ❌ Wave 0 (14-01) |
| OBS-01 | Logging failure is non-fatal (log and swallow) | unit | `pytest tests/test_approval_recorder.py::test_log_failure_nonfatal -x` | ❌ Wave 0 (14-01) |
| D-14 | SqliteDb `/approvals` does not 503 with POSTGRES_DSN unset | unit | `pytest tests/test_approval_recorder.py::test_sqlite_fallback_no_503 -x` | ❌ Wave 0 (14-01) |

### Sampling Rate

- **Per task commit:** `pytest tests/test_approval_recorder.py tests/test_telegram_adapter.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (tasks must create these)

- [ ] `tests/test_approval_recorder.py` — unit tests for DB method wrapping and OBS log emission
- [ ] Extend `tests/test_telegram_adapter.py` — new `TestApprovalBridge` class covering approve/deny bridge flows
- [ ] `agentos/approval_recorder.py` — created in 14-01 Wave 0 setup task

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Auth is phase 15 territory; not activated in phase 14 |
| V3 Session Management | no | — |
| V4 Access Control | partial | `/approvals/{id}/resolve` has user_isolation guard (currently inactive). Documented as phase 15 dependency. |
| V5 Input Validation | yes | `callback_data` validated in `handle_callback` (UUID regex, allowlisted agent_id). Bridge adds HTTP GET/POST — `run_id` and `tool_call_id` already validated before bridge is called. |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Duplicate Approve tap double-resolves row | Tampering | `_RESOLVED_RUNS` guard + 409 idempotency on `/approvals/{id}/resolve` |
| Resolve wrong approval row (multiple pending) | Tampering | Match by `tool_call_id`, not just "latest pending" |
| Resolve succeeds but continue fails — tool skipped silently | Repudiation | OBS log `op='resolve'` + Telegram error + `_RESOLVED_RUNS.discard` for retry |
| OBS log args dump leaks sensitive data | Information Disclosure | `tool_args_summary` truncated to ~100 chars; non-sensitive smoke inputs in phase 14 |
| Telegram user ID spoofed in `resolved_by` | Spoofing | `tg_user_id` comes from `query["from"]["id"]` (Telegram-signed). Acceptable for phase 14. |

---

## Sources

### Primary (HIGH confidence — verified in project venv source)
- `agno/run/approval.py` — `create_approval_from_pause`, `_build_approval_dict`, `check_and_apply_approval_resolution`, `update_approval_run_status` — all read directly from venv source.
- `agno/os/routers/approvals/router.py` — `GET /approvals`, `POST /approvals/{id}/resolve`, auth guard behavior — read directly.
- `agno/db/postgres/postgres.py:4813-4970` — all 7 approval DB methods with signatures — read directly.
- `agno/db/sqlite/sqlite.py:4661-4830` — sqlite approval method implementations confirmed — grep + partial read.
- `agno/agent/_run.py` — `handle_agent_run_paused` call chain, `check_and_apply_approval_resolution` at line 2973, `update_approval_run_status` at line 4854 — grep confirmed.
- `agno/agent/_tools.py` — `handle_tool_call_updates` confirmed/denied execution path — grep confirmed.
- `channels/telegram_adapter.py` — full source read; `handle_callback`, `send_approval_buttons`, `_PAUSED_TOOLS`, `_RESOLVED_RUNS` patterns confirmed.
- `agentos/instrumented_memory.py` — `_emit` pattern, logger boilerplate — full read.
- `agentos/eval_recorder.py` — `patch_classes_for_recording`, `_emit` pattern — partial read.
- `agentos/app.py` — shared `db` construction, instrumentation wiring sequence — full read.
- `agentos/tools/vault.py` — `@tool(requires_confirmation=True)` on `ingest_to_vault` and `research_topic` — full read.
- `.planning/phases/14-approvals-surface-activation/14-CONTEXT.md` — all decisions D-01 through D-17 — full read.
- `.planning/phases/10-diagnostic-audit/AUDIT.md` — `ai.agno_approvals` schema, root cause `RC-no-hitl-trigger-yet`, DIAG-BL-02 — grep confirmed.

### Secondary (MEDIUM confidence)
- `tests/test_telegram_adapter.py` — existing test patterns for callback validation, duplicate-tap regression — full read; confirms test structure to extend.
- `.planning/phases/13-knowledge-surface-activation/13-RESEARCH.md` — OBS-01 surface pattern precedent — partial read.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ai.agno_approvals.tool_call_id` is a top-level column in the DB row returned by `GET /approvals` | Code Examples / Bridge pattern | If not top-level, bridge must parse `requirements[]` JSON to match. Low risk: smoke path has single tool so `data[0]` works regardless. |
| A2 | `ApprovalResponse` schema (returned by `GET /approvals`) includes `tool_call_id` as a top-level field | Open Questions #1 | If absent, bridge matching logic needs adjustment. Verify in 14-01 unit test with real DB. |
| A3 | AgentOS auth is currently disabled (no JWT enforcement) for local/VPS deployment in phase 14 | Security Domain | If auth is inadvertently active, `POST /approvals/{id}/resolve` returns 404 for non-admin caller. Phase 14 scope; document as Phase 15 dependency. |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all from venv source, no packages to install
- Architecture: HIGH — all code paths traced in actual venv source files
- Pitfalls: HIGH — derived from actual code logic, not guesses
- OBS field schema: HIGH — mirrors existing _emit patterns directly

**Research date:** 2026-05-27
**Valid until:** Agno version upgrade (currently 2.6.7). Pin version; any venv upgrade requires re-verification of approval method signatures.
