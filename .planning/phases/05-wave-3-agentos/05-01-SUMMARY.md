---
phase: "05-wave-3-agentos"
plan: "05-01"
subsystem: "agentos"
tags: [postgres, memory-manager, mcp, a2a, wiring]
dependency_graph:
  requires: ["02-01", "03-01", "04-01", "04-02", "04-03", "04-04", "04-05"]
  provides: ["postgres-session-storage", "shared-memory-manager", "mcp-endpoint", "a2a-endpoint"]
  affects: ["agentos/app.py", "agentos/agents/supervisor.py"]
tech_stack:
  added: ["fastmcp>=2.0", "a2a-sdk>=0.2,<1.0"]
  patterns: ["factory-function", "shared-memory-manager", "mcp-server", "a2a-protocol"]
key_files:
  created: []
  modified:
    - "agentos/app.py"
    - "agentos/agents/supervisor.py"
    - "tests/test_agentos.py"
    - "requirements.txt"
decisions:
  - "PostgresDb used when POSTGRES_DSN_SESSIONS env var is set; SqliteDb fallback for dev/test"
  - "VaultKnowledge.knowledge used instead of make_knowledge() directly to avoid PgVector init failure when POSTGRES_DSN_KNOWLEDGE absent"
  - "enable_mcp_server=True set only on AgentOS() constructor (current Agno 2.6.7 does not accept it on get_app())"
  - "a2a-sdk pinned to <1.0 — v1.0.3 broke SendMessageSuccessResponse import that agno 2.6.7 expects from a2a.types"
metrics:
  duration: "5 minutes"
  completed: "2026-05-20"
  tasks_completed: 6
  files_changed: 4
---

# Phase 05 Plan 01: Wave 3 AgentOS Wiring Summary

PostgresDb session storage, shared MemoryManager, all 5 agent factories wired with memory+knowledge, MCP + A2A enabled on AgentOS.

## What Was Built

- `agentos/app.py` rewritten to use `PostgresDb` (when `POSTGRES_DSN_SESSIONS` env var is set) with `SqliteDb` fallback for dev/test environments
- Shared `MemoryManager` instantiated with `PostgresDb` backend and `cheap-worker` model
- `VaultKnowledge.knowledge` used to access the Knowledge instance (guards `PgVector` init when `POSTGRES_DSN_KNOWLEDGE` is absent)
- All 5 agent factories (`make_chat_agent`, `make_curator_agent`, `make_ingest_agent`, `make_query_agent`, `make_research_agent`) called with `memory_manager=memory` and `knowledge=kb` where applicable
- `AgentOS` constructed with `enable_mcp_server=True`, `a2a_interface=True`, `tracing=True`
- `supervisor.py` refactored: module-level `supervisor_agent = Team(...)` replaced by `make_supervisor_team(memory_manager, db)` factory function; backward-compat module-level instance retained
- Tests updated: 54 tests pass, including 3 new W3 assertions (PostgresDb/fallback check, MCP enabled, A2A enabled, supervisor factory signature)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `get_app()` does not accept `enable_mcp_server` kwarg**
- **Found during:** Task 4 (Wire AgentOS with MCP + A2A)
- **Issue:** Current Agno 2.6.7 `get_app()` signature is `(self) -> FastAPI`. The plan noted calling `get_app(enable_mcp_server=True)` but this is not supported — `get_app()` reads `self.enable_mcp_server` set during `AgentOS()` construction.
- **Fix:** Removed `enable_mcp_server=True` from `get_app()` call. Only the `AgentOS()` constructor kwarg is needed.
- **Files modified:** `agentos/app.py`

**2. [Rule 3 - Blocking] `fastmcp` package not installed**
- **Found during:** Task 4 — `enable_mcp_server=True` triggered `ModuleNotFoundError: No module named 'fastmcp'`
- **Fix:** Installed `fastmcp` via pip, added `fastmcp>=2.0` to `requirements.txt`
- **Files modified:** `requirements.txt`

**3. [Rule 3 - Blocking] `a2a-sdk` v1.0.3 incompatible with agno 2.6.7**
- **Found during:** Task 4 — `a2a_interface=True` triggered `ImportError: cannot import name 'SendMessageSuccessResponse' from 'a2a.types'`
- **Root cause:** `a2a-sdk` 1.0.3 moved `SendMessageSuccessResponse` to `a2a.compat.v0_3.types`; agno 2.6.7 expects it at `a2a.types`
- **Fix:** Downgraded to `a2a-sdk==0.2.16`, pinned `a2a-sdk>=0.2,<1.0` in requirements
- **Files modified:** `requirements.txt`

**4. [Rule 2 - Missing critical functionality] PostgresDb raises ValueError when DSN is None**
- **Found during:** Task 1 — `PostgresDb(db_url=None)` raises immediately during test imports
- **Fix:** Added conditional logic — PostgresDb when `POSTGRES_DSN_SESSIONS` is set, SqliteDb fallback otherwise. This ensures the app is importable in dev/test environments without a live Postgres instance.
- **Files modified:** `agentos/app.py`

**5. [Rule 2 - Missing critical functionality] `make_knowledge()` raises when POSTGRES_DSN_KNOWLEDGE is None**
- **Found during:** Testing Task 3 — direct call to `make_knowledge()` in `app.py` fails when DSN absent
- **Fix:** Replaced `kb = make_knowledge()` with `kb = vault.knowledge` — `VaultKnowledge` already guards this with a conditional (`if POSTGRES_DSN_KNOWLEDGE: make_knowledge() else: Knowledge()`).
- **Files modified:** `agentos/app.py`

## Verification

All 54 tests pass:
- `tests/test_agentos.py` — 28 tests (all new W3 assertions included)
- `tests/test_core.py` — 8 tests
- `tests/test_telegram_adapter.py` — 18 tests

Must-have checklist:
- [x] `agentos/app.py` uses PostgresDb (when POSTGRES_DSN_SESSIONS set) or SqliteDb fallback
- [x] Shared MemoryManager instantiated with db backend
- [x] AgentOS constructor called with `enable_mcp_server=True` and `a2a_interface=True`
- [x] `get_app()` called without extra kwargs (Agno 2.6.7 does not need it)
- [x] All 5 agents receive `memory_manager=` and `knowledge=` from app.py
- [x] Existing tests pass (54/54 green)

## Known Stubs

None — all agent connections are real (not hardcoded empty values). The SqliteDb fallback is intentional behavior for dev environments, not a stub.

## Self-Check: PASSED
