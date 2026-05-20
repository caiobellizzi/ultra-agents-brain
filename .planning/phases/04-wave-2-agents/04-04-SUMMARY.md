---
phase: "04-wave-2-agents"
plan: "04-04"
subsystem: "agents/query"
tags: ["rag", "memory", "reasoning", "output-schema"]
dependency_graph:
  requires: ["04-01"]
  provides: ["query agent full stack"]
  affects: ["agentos/agents/query.py"]
tech_stack:
  added: ["ReasoningTools", "MemoryManager", "AgentAsJudgeEval", "QueryAnswer"]
  patterns: ["factory function with module-level backward-compat instance"]
key_files:
  modified: ["agentos/agents/query.py"]
decisions:
  - "Followed chat.py pattern: factory function + module-level query_agent for backward compat"
  - "evals= kwarg not wired (Agno doesn't expose it yet); citation_judge held as _ placeholder"
  - "Model bumped from cheap-worker to default-worker"
metrics:
  duration: "~3 minutes"
  completed: "2026-05-20"
  tasks_completed: 1
  files_modified: 1
---

# Phase 04 Plan 04: Query Agent Reconfiguration Summary

Query agent upgraded to full conversational stack: MemoryManager, session summaries, vault RAG (search_knowledge=True), ReasoningTools, and typed QueryAnswer output schema. Model bumped from cheap-worker to default-worker.

## What Was Built

`agentos/agents/query.py` refactored from a bare module-level Agent instantiation to a `make_query_agent(memory_manager, knowledge, db)` factory function, matching the pattern established in chat.py. A module-level `query_agent` instance is still exported for backward compatibility with tests and app.py.

## Must-Haves Verification

| Requirement | Status |
|---|---|
| memory_manager=, enable_agentic_memory=True, update_memory_on_run=True | PASS |
| Session summaries (enable_session_summaries=True etc.) | PASS |
| knowledge= and search_knowledge=True | PASS |
| output_schema=QueryAnswer | PASS |
| ReasoningTools(add_instructions=True) in tools | PASS |
| Model bumped to default-worker | PASS |
| All tests pass | PASS (48/48) |

## Deviations from Plan

**1. [Rule 1 - Bug] evals= kwarg skipped**
- Same as chat.py: current Agno version does not accept `evals=` on Agent
- citation_judge defined and held as `_ = citation_judge` for future wiring
- No tests broken

## Self-Check: PASSED

- File exists: `agentos/agents/query.py` - FOUND
- Commit `9853e84` - FOUND
- 48 tests pass - VERIFIED
