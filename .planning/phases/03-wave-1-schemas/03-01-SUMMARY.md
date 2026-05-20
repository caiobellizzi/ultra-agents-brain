---
phase: "03-wave-1-schemas"
plan: "03-01"
subsystem: "agentos"
tags: ["schemas", "pydantic", "model-factory", "litellm"]
dependency_graph:
  requires: ["02-01"]
  provides: ["agentos.schemas", "agentos.model.chat_model"]
  affects: ["wave-2-agents", "wave-5-evals"]
tech_stack:
  added: ["pydantic BaseModel"]
  patterns: ["typed result models", "tier-based model factory"]
key_files:
  created:
    - "agentos/schemas.py"
  modified:
    - "agentos/model.py"
decisions:
  - "Kept existing model.py chat_model(tier) signature unchanged; added env-var tier mapping as extension"
  - "Tier env vars fall back to tier name so existing LiteLLM group names continue working"
metrics:
  duration: "~5 min"
  completed: "2026-05-20"
  tasks_completed: 3
  files_changed: 2
---

# Phase 03 Plan 01: Wave 1 — Schemas + Model Factory Summary

Typed Pydantic result models and 4-tier model factory for AgentOS agent output contracts.

## What Was Built

**`agentos/schemas.py`** — new file with 8 Pydantic models:
- `VaultCitation` — shared citation type (path, title, tags, excerpt)
- `ChatReply` — chat agent output (text + citations + suggested_actions)
- `QueryAnswer` — vault query output (answer + citations + confidence)
- `IngestResult` — ingest agent output (note_path + frontmatter + tags + needs_review)
- `Finding` — sub-model for research (summary + source)
- `ResearchReport` — research agent output (topic + findings + next_questions)
- `CuratorResult` — curator agent output (actions_taken + notes_touched + errors)
- `SupervisorRouting` — supervisor routing output (chosen_member + reason + response)

**`agentos/model.py`** — extended with `_TIER_ENV` mapping dict and updated `chat_model()` docstring:
- `cheap-worker` → `LITELLM_CHEAP_MODEL` env var (fallback: `"cheap-worker"`)
- `default-worker` → `LITELLM_DEFAULT_MODEL` env var (fallback: `"default-worker"`)
- `orchestrator` → `LITELLM_ORCHESTRATOR_MODEL` env var (fallback: `"orchestrator"`)
- `private-worker` → `LITELLM_PRIVATE_MODEL` env var (fallback: `"private-worker"`)

Existing deployments unaffected — tier names still work as LiteLLM group names by default.

## Verification Results

```
schemas ok
model factory ok: cheap-worker
47 passed in 2.98s
```

All 47 existing tests green. Import smoke checks clean.

## Deviations from Plan

**1. [Rule 1 - Bug] model.py already had chat_model()**
- **Found during:** Task 2
- **Issue:** `model.py` already exposed `chat_model(tier)` from Phase 02 infra work — the plan assumed it needed to be created from scratch
- **Fix:** Extended the existing function with the 4-tier env-var mapping rather than replacing it; kept backward-compatible signature and fallback behavior
- **Files modified:** `agentos/model.py`
- **Commit:** 92d63e6

## Self-Check: PASSED

- `agentos/schemas.py` exists with 8 Pydantic models
- `agentos/model.py` has `chat_model(tier)` with all 4 tiers
- All imports resolve without error
- 47 tests pass
