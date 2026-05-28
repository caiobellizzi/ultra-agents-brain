---
phase: 14-approvals-surface-activation
reviewed: 2026-05-28T14:15:00-03:00
depth: standard
files_reviewed: 6
files_reviewed_list:
  - agentos/app.py
  - agentos/approval_recorder.py
  - agentos/tools/vault.py
  - channels/telegram_adapter.py
  - tests/test_approval_recorder.py
  - tests/test_telegram_adapter.py
findings:
  critical: 4
  warning: 4
  info: 3
  total: 11
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-05-28T14:15:00-03:00
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 14 adds the HITL approvals surface: `approval_recorder.py` monkey-patches three
Agno DB approval methods to emit OBS-01 structured logs; `app.py` wires the patch at
startup; `vault.py` applies `@approval` + `@tool(requires_confirmation=True)` to two
HITL tools; and `telegram_adapter.py` bridges Telegram inline button callbacks to the
Agno `/approvals` resolution API.

Four critical issues were found: (1) `tool_args_summary` writes up to 120 raw characters
of tool argument values into the OBS log -- sufficient to leak a full private file path
or sensitive research query, defeating the stated T-14-03 mitigation; (2) `_RESOLVED_RUNS`
and `_PAUSED_TOOLS` are unbounded module-level structures with no TTL eviction;
(3) the decorator order on both HITL tools in `vault.py` is inverted, placing `@approval`
outside `@tool`; and (4) two tests in `test_telegram_adapter.py` assert the routing
default is `"supervisor"` but the implementation returns `"chat"` -- these tests fail
today and prove the test suite was not run after the Phase 11-02 routing change.

---

## Critical Issues

### CR-01: `tool_args_summary` logs raw argument values -- T-14-03 mitigation is a length cap, not a data filter

**File:** `agentos/approval_recorder.py:70`

**Issue:** The module docstring declares T-14-03 mitigated: "tool_args truncated to
`str(args)[:120]`; raw args never logged." This claim is false.
`str({"source": "file:///srv/second-brain/private/diary.md"})` is 52 characters and fits
entirely within the 120-char cap, emitted verbatim to the `agentos.approval` logger.
A `research_topic` call with `topic="my mental health situation and anxiety"` similarly
fits. The log propagates to every configured log shipper, aggregator, and stdout sink.
The stated invariant ("raw args never logged") is violated by design.

**Fix:** Replace the raw `str()` truncation with a structural summary that logs only
key names and value shapes, never values:

```python
tool_args_summary = ", ".join(
    f"{k}:<{type(v).__name__}:{len(str(v))}chars>"
    for k, v in (approval_data.get("tool_args") or {}).items()
)[:120]
```

Alternatively, maintain an explicit allowlist of safe-to-log arg names (e.g.
`max_workers`) and mask everything else.

---

### CR-02: `_RESOLVED_RUNS` and `_PAUSED_TOOLS` grow without bound -- memory leak and stale tool replay risk

**File:** `channels/telegram_adapter.py:29-32`

**Issue:** `_RESOLVED_RUNS` is a module-level `set[str]`. Run IDs are added at line 538
and only conditionally discarded on specific error paths. In a long-running process every
approved or denied run accumulates a permanent entry. `_PAUSED_TOOLS` pops on the success
path (line 556) but is left populated when `_resolve_approval_row` returns `False`
(lines 543-545 discard from `_RESOLVED_RUNS` for retry but no corresponding
`_PAUSED_TOOLS` cleanup occurs). Over process lifetime both structures grow without bound.

Beyond memory, stale `_PAUSED_TOOLS` entries create a correctness hazard: a crafted
duplicate callback arriving after the original run has expired on the AgentOS side will
replay the cached `tool_execution` dict verbatim to `/continue`, potentially
re-triggering a tool call in an unrelated context.

**Fix:** Replace the bare `set` with a bounded LRU map with TTL. Add at module level:

```python
import time
from collections import OrderedDict

_MAX_CACHE = 500
_TTL_SECONDS = 3600

_RESOLVED_RUNS: OrderedDict  # run_id -> monotonic timestamp (replace bare set)

def _mark_resolved(run_id: str) -> None:
    _RESOLVED_RUNS[run_id] = time.monotonic()
    if len(_RESOLVED_RUNS) > _MAX_CACHE:
        _RESOLVED_RUNS.popitem(last=False)

def _is_resolved(run_id: str) -> bool:
    ts = _RESOLVED_RUNS.get(run_id)
    if ts is None:
        return False
    if time.monotonic() - ts > _TTL_SECONDS:
        del _RESOLVED_RUNS[run_id]
        return False
    return True

def _release_resolved(run_id: str) -> None:
    _RESOLVED_RUNS.pop(run_id, None)
    _PAUSED_TOOLS.pop(run_id, None)
```

Replace `_RESOLVED_RUNS.add`, `run_id in _RESOLVED_RUNS`, and `_RESOLVED_RUNS.discard`
calls with the helpers above.

---

### CR-03: Decorator order on HITL tools is inverted -- `@approval` wraps the Agno tool descriptor, not the callable

**File:** `agentos/tools/vault.py:36-47, 58-70`

**Issue:** Python applies decorators bottom-up. The current stack:

```python
@approval                          # applied second -- wraps the @tool result
@tool(requires_confirmation=True)  # applied first -- converts def to Agno descriptor
def ingest_to_vault(source: str) -> str:
```

`@tool(requires_confirmation=True)` runs first and converts `ingest_to_vault` into an
Agno tool descriptor. `@approval` then wraps that descriptor. If `@approval` is intended
to gate the raw Python callable, it is instead receiving an already-processed Agno object.
The gate is either bypassed or misfiring depending on how Agno resolves the callable at
dispatch time. Smoke tests may pass if Agno introspects through the outer wrapper, but
the behaviour under `deep_copy` and class-level agent reset (app.py lines 64-71) is
undefined.

Confirm: `type(ingest_to_vault)` in a REPL should return an Agno tool type. If it
returns whatever `@approval` produces, the order is wrong.

**Fix:** Reverse so `@approval` is innermost:

```python
@tool(requires_confirmation=True)
@approval
def ingest_to_vault(source: str) -> str:
    ...

@tool(requires_confirmation=True)
@approval
def research_topic(topic: str, *, max_workers: int = 3) -> str:
    ...
```

---

### CR-04: Two tests assert routing default is `"supervisor"` but code returns `"chat"` -- test suite fails

**File:** `tests/test_telegram_adapter.py:47-48, 64`

**Issue:** `test_plain_text_routes_to_supervisor` (line 47-48) calls
`_agent_id_for("Hello, how are you?")` and asserts `"supervisor"`.
`test_unknown_command_falls_back_to_supervisor` (line 64) asserts the same for
`/unknown something`. The implementation at `telegram_adapter.py:248` returns `"chat"` as
the default -- changed in the Phase 11-02 follow-up (documented in the inline comment at
lines 228-235 of the adapter). Both assertions will fail. The test suite cannot pass as
written, which undermines confidence in the security tests (`TestCallbackDataValidation`,
`TestApprovalBridge`) in the same file.

**Fix:**

```python
def test_plain_text_routes_to_chat(self):
    agent = self.mod._agent_id_for("Hello, how are you?")
    self.assertEqual(agent, "chat")

def test_unknown_command_falls_back_to_chat(self):
    agent = self.mod._agent_id_for("/unknown something")
    self.assertEqual(agent, "chat")
```

---

## Warnings

### WR-01: Fallback `rows[0]` silently resolves the wrong approval on multi-tool runs

**File:** `channels/telegram_adapter.py:458-459`

**Issue:** When no row's `tool_execution.tool_call_id` matches the one from
`callback_data`, the code falls back to `rows[0]`. On a run paused with two simultaneous
HITL tool calls, tapping "Approve" on tool B may update tool A's DB row if tool B's
`tool_call_id` appears second in the query result. The run then has inconsistent state:
tool A's row is resolved, tool B's row remains pending, and `/continue` proceeds with
the wrong confirmation recorded.

**Fix:** Remove the fallback and treat no-match as a hard failure:

```python
if approval_id is None:
    log.warning(
        "No pending approval row matched tool_call_id=%s for run=%s (available: %s)",
        tool_call_id,
        run_id,
        [r.get("id") for r in rows],
    )
    return False
```

---

### WR-02: `tool_call_id` from `callback_data` is not UUID-validated -- inconsistent with `run_id` guard

**File:** `channels/telegram_adapter.py:518, 455`

**Issue:** `run_id` is validated against `_UUID_RE` (line 525) before use. `tool_call_id`
originates from the same untrusted `callback_data` string (line 518) and receives no
equivalent validation. It is used directly in the match expression at line 455 and passed
into GET query params at line 440. The current matching is against DB data (safe), but
the absence of validation is inconsistent with the explicit `run_id` guard and leaves a
gap for future callers or log injection if error messages include the raw value.

**Fix:** Add a UUID check for `tool_call_id` immediately after the `run_id` check:

```python
if not _UUID_RE.match(tool_call_id):
    log.warning("callback_data contains invalid tool_call_id %r -- ignoring", tool_call_id)
    return
```

---

### WR-03: `_PAUSED_TOOLS` is popped before `/continue` POST -- retry after continue failure uses incomplete stub

**File:** `channels/telegram_adapter.py:556, 583-602`

**Issue:** `_PAUSED_TOOLS.pop(run_id, None)` executes at line 556, before the `/continue`
POST at line 583. If the POST fails with a non-409 status (lines 597-602),
`_RESOLVED_RUNS.discard(run_id)` releases the retry gate, but `_PAUSED_TOOLS` is already
empty. The subsequent retry tap uses the minimal one-element stub (lines 565-568) that
omits `tool_name`, `tool_args`, and other fields Agno needs. The retry will fail or
produce incorrect behaviour even though the user is told they can try again.

**Fix:** Peek without popping, then discard only after confirmed success:

```python
cached = _PAUSED_TOOLS.get(run_id)  # peek, do not pop
# ... build tools_list from cached ...
try:
    r = await client.post(continue_url, data=continue_data)
except httpx.RequestError as exc:
    if cached is not None:
        _PAUSED_TOOLS[run_id] = cached  # restore for retry
    ...
    return
if r.status_code not in (200, 201) and not (
    r.status_code == 409 and "already continued" in r.text
):
    if cached is not None:
        _PAUSED_TOOLS[run_id] = cached  # restore for retry
    _RESOLVED_RUNS.discard(run_id)
    await send_message(client, chat_id, f"AgentOS error resuming run: {r.status_code}")
    return
_PAUSED_TOOLS.pop(run_id, None)  # discard only after confirmed success
```

---

### WR-04: `wrapped_update_approval` emits `run_id=None` -- OBS correlation broken for resolve events

**File:** `agentos/approval_recorder.py:108-117`

**Issue:** `wrapped_update_approval` hardcodes `run_id=None` in the `_emit` call
(line 109). The `update_approval` method signature does not receive `run_id`, but the DB
result dict likely contains it. Without `run_id` in resolve-event OBS records, correlating
`create` -> `resolve` -> `run_status` events in a log query requires joining on
`approval_id`, which may not be indexed in all log aggregation backends.

**Fix:**

```python
run_id_from_result = (result or {}).get("run_id")
recorder._emit(
    op="resolve",
    approval_id=approval_id,
    ...
    run_id=run_id_from_result,
    ...
)
```

---

## Info

### IN-01: Logger propagation is environment-sensitive -- behaviour differs between test and production

**File:** `agentos/approval_recorder.py:26-30`

**Issue:** The handler setup block at lines 26-30 adds a `StreamHandler` and sets
`log.propagate = False` only when neither the named logger nor the root logger has
handlers. In production (JSON shipper on root logger) the block is skipped and `propagate`
stays `True`. In a bare test environment a `StreamHandler` is added and
`propagate = False`, silencing the parent. Logger behaviour differs between environments
in a way that could mask OBS gaps during development.

**Fix:** Remove the inline handler bootstrapping entirely and rely on the application's
logging configuration. If an OBS log handler is required unconditionally, configure it
in `app.py`'s startup sequence rather than inside the library module.

---

### IN-02: `tool_args_summary` conditionally absent in OBS record schema -- downstream parsers need documentation

**File:** `agentos/approval_recorder.py:198-199`

**Issue:** `tool_args_summary` is included in the JSON record only when not `None`
(line 198), appearing only on `op=create` events. Log parsers expecting a fixed schema
will silently miss the field on `resolve` and `run_status` records.

**Fix:** Document in the module docstring that `tool_args_summary` is only present on
`op=create` events. Optionally emit `"tool_args_summary": null` unconditionally for a
consistent schema.

---

### IN-03: `BOT_TOKEN` embedded in `TG_API` constant -- future URL-logging calls would leak the token

**File:** `channels/telegram_adapter.py:61`

**Issue:** `TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"` bakes the token into a
module-level string constant. Current log call sites log only `exc` or status codes, not
request URLs, so the token is not currently leaked. However, any new
`log.error(..., r.request.url)` or httpx debug-level logging would expose the full URL
including the token in every log sink.

**Fix:** Construct the token-containing URL transiently at call sites only:

```python
_TG_BASE = "https://api.telegram.org"

async def tg_get(client, method, **params):
    resp = await client.get(f"{_TG_BASE}/bot{BOT_TOKEN}/{method}", params=params)
```

This avoids storing the token in a loggable module-level constant.

---

_Reviewed: 2026-05-28T14:15:00-03:00_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
