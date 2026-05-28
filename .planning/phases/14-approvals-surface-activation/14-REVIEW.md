---
phase: 14-approvals-surface-activation
reviewed: 2026-05-28T13:57:00-03:00
depth: standard
files_reviewed: 4
files_reviewed_list:
  - agentos/approval_recorder.py
  - agentos/app.py
  - agentos/tools/vault.py
  - channels/telegram_adapter.py
findings:
  critical: 3
  warning: 4
  info: 3
  total: 10
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-05-28T13:57:00-03:00
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 14 adds the HITL approvals surface: `approval_recorder.py` monkey-patches three Agno `PostgresDb` approval methods to emit OBS-01 structured logs; `app.py` wires the patch at startup; `vault.py` adds `@approval` + `@tool(requires_confirmation=True)` to two HITL tools; and `telegram_adapter.py` adds `_resolve_approval_row` to reconcile the native approval row before calling `/continue`.

The overall architecture is sound and the threat mitigations in `approval_recorder.py` are well-considered. However, three critical issues surfaced: (1) `tool_args_summary` logs 120 characters of raw `str()` output from potentially sensitive vault content — the stated truncation is insufficient protection; (2) `_RESOLVED_RUNS` and `_PAUSED_TOOLS` are unbounded in-memory sets/dicts that grow forever, creating a memory leak and a stale-state attack surface; (3) the `@approval` / `@tool` decorator stack in `vault.py` is applied in a potentially wrong order that may cause `@approval` to wrap the Agno `ToolCallInfo` wrapper instead of the underlying function.

---

## Critical Issues

### CR-01: `tool_args_summary` logs raw vault content — T-14-03 mitigation is incomplete

**File:** `agentos/approval_recorder.py:70`

**Issue:** The docstring claims "raw args never logged" and T-14-03 is listed as mitigated by truncating to `str(args)[:120]`. However, `str({})` on a vault ingest payload (e.g. `{'source': 'file:///srv/second-brain/private/diary.md'}`) or a research topic (e.g. `{'topic': 'my health condition ...'`) faithfully encodes the full first 120 characters of potentially sensitive PII. The truncation is a length cap, not a data-class filter. A private file path or a sensitive research query fits entirely in 120 chars. The OBS-01 log is written to `agentos.approval` which propagates to the root logger — it will appear in application logs, log aggregators, and any log-shipping pipeline.

**Fix:** Replace the raw-str truncation with explicit field extraction that logs only safe metadata:

```python
# Approved: log only key names and value type/length, never the value itself
tool_args_summary = ", ".join(
    f"{k}:<{type(v).__name__}:{len(str(v))}chars>"
    for k, v in (approval_data.get("tool_args") or {}).items()
)[:120]
```

Alternatively, maintain an explicit allowlist of args that are safe to log (e.g. `max_workers`) and mask everything else.

---

### CR-02: `_RESOLVED_RUNS` and `_PAUSED_TOOLS` grow without bound — memory leak + stale SSRF surface

**File:** `channels/telegram_adapter.py:32,139`

**Issue:** `_RESOLVED_RUNS` is a module-level `set[str]` and `_PAUSED_TOOLS` is a `dict[str, list[dict]]`. Run IDs are added to `_RESOLVED_RUNS` on first approval (line 139) and never evicted. `_PAUSED_TOOLS` pops on success (line 157) but not on denial-without-continue or on adapter restart crash paths. Over the lifetime of the process (the adapter runs continuously), both structures accumulate indefinitely. On a busy instance this is a slow memory leak; more importantly, a stale `_PAUSED_TOOLS` entry for an old `run_id` can be replayed if a crafted callback arrives with that run_id after the original run has expired from the AgentOS side — the cached `tool_execution` dict will be sent verbatim to `/continue`, potentially re-triggering a tool in a new context.

**Fix:**

```python
import time
from collections import OrderedDict

_MAX_CACHE = 500
_RESOLVED_RUNS: dict[str, float] = OrderedDict()  # run_id -> timestamp
_PAUSED_TOOLS: dict[str, list[dict]] = {}

def _mark_resolved(run_id: str) -> None:
    _RESOLVED_RUNS[run_id] = time.monotonic()
    if len(_RESOLVED_RUNS) > _MAX_CACHE:
        _RESOLVED_RUNS.popitem(last=False)  # evict oldest

def _is_resolved(run_id: str) -> bool:
    ts = _RESOLVED_RUNS.get(run_id)
    if ts is None:
        return False
    if time.monotonic() - ts > 3600:  # 1-hour TTL
        del _RESOLVED_RUNS[run_id]
        return False
    return True
```

Replace `_RESOLVED_RUNS.add(run_id)` / `_RESOLVED_RUNS.discard(run_id)` / `run_id in _RESOLVED_RUNS` with the above helpers.

---

### CR-03: Decorator order on HITL tools is inverted — `@approval` wraps `@tool` output, not the raw callable

**File:** `agentos/tools/vault.py:36-47, 58-70`

**Issue:** Python decorators apply bottom-up. The current stack is:

```python
@approval          # applied second — wraps the result of @tool(...)
@tool(requires_confirmation=True)  # applied first — wraps ingest_to_vault
def ingest_to_vault(source: str) -> str:
```

`@tool(requires_confirmation=True)` converts `ingest_to_vault` into an Agno `ToolCallInfo` object (or similar wrapper). `@approval` then wraps that wrapper. The correct intended order (based on Agno's decorator contract) should be `@tool` outermost so that Agno's tool registration machinery sees the function decorated by `@approval`. If `@approval` is the Agno approval-gate decorator, it must be the innermost layer so that it wraps the raw Python callable — not the already-processed tool descriptor.

The root cause noted in the task context ("@approval decorator was missing") was fixed in commit 2cb0eb9, but the stack order was not verified. If tools appear to work in smoke tests, it may be because Agno's `@tool` unwraps the callable to inspect it; however, the behaviour under `deep_copy` and class-level agent reset (discussed in `app.py` comment) is undefined when the decorator chain is inverted.

**Fix:** Reverse the decorator order so `@approval` is innermost:

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

Verify by calling `type(ingest_to_vault)` in a REPL — it should be an Agno tool type, not whatever `@approval` returns.

---

## Warnings

### WR-01: Fallback `approval_id` selection picks `rows[0]` — wrong row on multi-tool runs

**File:** `channels/telegram_adapter.py:59-60`

**Issue:** When no row's `tool_call_id` matches, `_resolve_approval_row` falls back to `rows[0]`. On a run that pauses with multiple tool calls (e.g., two HITL tools queued), `rows[0]` may be the row for a *different* tool than the one the user tapped. This silently resolves the wrong approval row, which means one tool gets its DB record updated while the other does not, leading to an inconsistent approval state.

**Fix:** Remove the fallback and treat "no matching row" as a hard failure:

```python
if approval_id is None:
    log.warning(
        "No pending approval row matched tool_call_id %s for run %s "
        "(rows available: %s)",
        tool_call_id,
        run_id,
        [r.get("id") for r in rows],
    )
    return False
```

---

### WR-02: `tool_call_id` is not validated — arbitrary URL segment in `/approvals/{id}/resolve`

**File:** `channels/telegram_adapter.py:68`

**Issue:** `approval_id` is extracted from the GET `/approvals` response — it comes from the server, so it is relatively trusted. However, `tool_call_id` comes from Telegram `callback_data`, is split on `:` and used directly in the GET query param and passed to `_resolve_approval_row`. `tool_call_id` is then matched against `row["tool_execution"]["tool_call_id"]` in the DB response, which is safe. But `run_id` is validated by UUID regex (line 126), while `tool_call_id` receives no validation at all. A crafted `callback_data` with a `tool_call_id` like `../../../admin` would propagate into the GET params and be matched against DB data — it would not find a row and return `False`, but it is still untrusted user data touching a query parameter without sanitisation.

**Fix:** Add a UUID regex check for `tool_call_id` alongside the existing `run_id` check:

```python
if not _UUID_RE.match(tool_call_id):
    log.warning("callback_data contains invalid tool_call_id %r — ignoring", tool_call_id)
    return
```

---

### WR-03: `wrapped_update_approval` does not log `run_id` — OBS correlation is broken for resolve events

**File:** `agentos/approval_recorder.py:96-126`

**Issue:** `wrapped_update_approval(approval_id, expected_status, **kwargs)` emits a log record with `run_id=None` (line 109). The `update_approval` Agno method signature does not receive `run_id` — but the original `result` dict returned by the DB call likely contains it. Not including `run_id` in resolve-event logs breaks the ability to correlate `create` → `resolve` → `run_status` events in a log query by `run_id` alone; analysts must join on `approval_id` instead.

**Fix:**

```python
run_id_from_result = (result or {}).get("run_id")
recorder._emit(
    ...
    run_id=run_id_from_result,
    ...
)
```

---

### WR-04: `_PAUSED_TOOLS` is not cleaned up on denial path

**File:** `channels/telegram_adapter.py:157-170`

**Issue:** `_PAUSED_TOOLS.pop(run_id, None)` is called regardless of `confirmed`, so the cache is cleaned on both approve and deny. However, if `_resolve_approval_row` returns `False` (lines 144-147), the function returns early after re-inserting `run_id` into `_RESOLVED_RUNS` via discard but the `_PAUSED_TOOLS` entry is never popped. The user is told "Approval update failed — please try again." but if they tap again, the code re-enters `handle_callback`, finds `run_id in _RESOLVED_RUNS` (it was added at line 139 before the failure), and drops the retry silently (line 137-138).

**Fix:** The `_RESOLVED_RUNS.discard(run_id)` rollback (line 146) is correct for allowing retry, but the inconsistency between `_RESOLVED_RUNS` rollback and missing `_PAUSED_TOOLS` cleanup on `_resolve_approval_row` failure is confusing. Document explicitly that `_PAUSED_TOOLS` is intentionally left populated on this path (so the retry can use the cached tools) or add a cleanup call. Also note that this interacts with CR-02: if retry never succeeds, `_PAUSED_TOOLS` leaks the entry.

---

## Info

### IN-01: Logger `propagate = False` may suppress structured log shipping

**File:** `agentos/approval_recorder.py:30`

**Issue:** `log.propagate = False` is set only when a new handler is added (lines 26-30). If the root logger already has handlers (as it will in production, e.g. a JSON log shipper), no handler is added and `propagate` stays `True`. The condition `if not log.handlers and not logging.getLogger().handlers` means the guard is environment-dependent. This is fragile; in a container with structlog or a JSON formatter configured on the root, `log.propagate = True` plus no local handler is correct — but a bare test environment gets a StreamHandler added and `propagate = False`, silencing the parent. The inconsistency makes log routing hard to reason about.

**Fix:** Either remove the inline handler setup entirely and rely on the application's logging config, or always set `propagate = False` and explicitly add the handler unconditionally (and accept that test output goes to stderr).

---

### IN-02: `tool_args_summary` field included only when not `None` — schema inconsistency

**File:** `agentos/approval_recorder.py:198-199`

**Issue:** The OBS-01 log record conditionally includes `tool_args_summary` only for `create` events. `resolve` and `run_status` events omit it. While intentional (those calls don't have args), downstream log parsers that expect a fixed schema will need to handle optional presence. The pattern is inconsistent with `error_type` / `error_msg` which are also conditional but are documented as optional in the docstring.

**Fix:** Document in the module docstring that `tool_args_summary` is only present on `op=create` events to set parser expectations.

---

### IN-03: `BOT_TOKEN` in module-level `TG_API` constant leaks token into log lines at WARNING level

**File:** `channels/telegram_adapter.py:61`

**Issue:** `TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"` is used as the base URL for all Telegram calls. Several `log.warning(...)` calls (e.g., line 199: `"Continue returned %s: %s", r.status_code, r.text[:200]`) include `r.request.url` or other request-level attributes in some httpx versions. More critically, if an `httpx.RequestError` is ever logged with the full URL (not currently — only `exc` is logged — but fragile), the bot token appears in logs. The safer pattern is to never construct URLs containing the token, or to use httpx's base_url + auth header approach.

**Fix:** Use httpx's `base_url` + token-as-path-segment only in the client, or at minimum ensure no `log.*` call ever includes request URLs:

```python
# Safer: store token separately, build URLs in helpers only
_TG_BASE = "https://api.telegram.org"
_TG_PATH_PREFIX = f"/bot{BOT_TOKEN}"  # never logged
```

This is a low-severity concern given the current log call sites, but worth noting before adding any new `log.error("... %s", exc)` where `exc` might carry URL context.

---

_Reviewed: 2026-05-28T13:57:00-03:00_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
