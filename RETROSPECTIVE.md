# ultra-agents-brain v2.0 Retrospective

**Milestone:** AgentOS Surface Activation
**Phases:** 10–18 (9 phases)
**Period:** ~May 2026

## What shipped

| Phase | Name | Status | Key deliverable |
|-------|------|--------|-----------------|
| 10 | AgentOS Migration + PostgreSQL | ✓ | SQLite → Postgres, AgentOS host |
| 11 | Memory Surface Activation | ✓ | InstrumentedMemoryManager, OBS-01 logging |
| 12 | Evals Surface Activation | ✓ | eval_recorder live patches, live judge worker |
| 13 | Knowledge Surface Activation | ✓ | pgvector vault reindex, make_knowledge wiring |
| 14 | Approvals Surface Activation | ✓ | Telegram HITL inline buttons, callback_data auth |
| 15 | worker.monitor Polish + Final Verification | ✓ | MON-01 date-mismatch fix, MON-02 regression tests, check-surfaces |
| 16 | Brain Vault Overhaul | ✓ | TELOS fill, inbox sweep, vault registry |
| 17 | Multi-repo brain pipelines | ✓ | GitHub Actions reusable workflows |
| 18 | Auto-sync second-brain | ✓ | VPS deploy key, git-sync.sh, launchd sync |

## Key decisions

- **SQLite → PostgreSQL (Phase 10):** Needed for pgvector, AgentOS dashboard, and
  multi-process access on VPS. Agno's SqliteDb has no migration story.

- **Single shared PostgresDb (Phase 13):** `POSTGRES_DB` singleton in `agentos/db.py`
  — avoids N connections and ensures knowledge + memory see the same schema.

- **eval_recorder via class-level monkey-patch (Phase 12):** Patches `Agent.run` /
  `Agent.arun` at import time so all agents are instrumented without code changes.
  Known limitation: streaming runs not recorded.

- **Telegram HITL via callback_data (Phase 14):** Agno's native `requires_confirmation=True`
  wired to inline keyboard buttons. UUID validation prevents arbitrary callback injection.

- **2-pass vault sync (Phase 18):** Pull-first strategy (VPS → Mac, no `--delete`) then
  push (Mac → VPS, `--delete`) protects VPS-generated Inbox items from deletion.

- **TELOS scoring for inbox routing (Phase 16):** Items >= 0.6 → articles/, < 0.3 →
  auto-culled/, 0.3–0.6 → Inbox (read by brief).

## Known gaps not closed

- `model_id` is null in all live eval rows (Agno `RunOutput.model` returns tier name
  string, not typed Model object with `.id`)
- Streaming and background agent runs bypass eval_recorder entirely
- `check-surfaces` approvals count likely 0 in production (no approval requests generated
  since Phase 14)

## Surprises

- Phase 18 required a VPS deploy key as a prerequisite not in the original plan — added
  as Phase 18-01
- iCloud APFS `.unlink()` fails silently on mounted shares; had to switch to
  `move_to_trash()` (Phase 16-05)
- `date.today()` mismatch between monitor and brief crons caused all evening-filed items
  to be missed by next morning's brief (MON-01, Phase 15)

## Lessons

- `/gsd:discuss-phase` before each phase produced tighter, better-verified plans —
  phases with CONTEXT.md executed faster
- Nyquist validation gaps found real missing tests in phases 12–14
- VPS env var loading order matters: `set -a; source .env; set +a` needed before
  subprocess spawns

---

## Post-v2.0: Self-Evolving Agents

**Work window:** May 2026 (after v2.0 closed)

### What shipped

| Feature | Deliverable |
|---------|------------|
| Eval noise fixes | eval_recorder no longer records junk/Untitled rows; HITL rows excluded |
| Live auto-scoring | uab-live-judge.service + timer fires every 2 min; judges pending eval rows via LLM |
| Experience KB | live_judge._write_experience_note() writes judgments to vault/_system/experiences/{agent_id}/ |
| Agentic Culture | enable_agentic_culture=True on all 5 leaf agents (chat, query, research, ingest, curator) |
| Supervisor agent | agentos/agents/supervisor.py — Agno Team orchestrating all 5 leaf agents |
| Workshop system | workshop_queue.py + workshop_registry.py — cross-session autonomous work queue |

### Key decisions

- **Experience notes in vault, not DB:** Judgment summaries written to markdown vault notes so agents can search them through the Knowledge surface without a separate vector store

- **Class-level culture enabling:** `enable_agentic_culture=True` passed to `create_agent()` so culture KB is inherited at construction, not injected at runtime

- **Reindex failure accepted for now:** live_judge calls `reindex()` after writing experience notes, but `create_knowledge` is not yet available in `agentos.knowledge` — the note is written successfully, the reindex is skipped with a warning (not a hard failure)

### Known gaps not closed

- `create_knowledge` missing from agentos.knowledge — experience notes written but not auto-reindexed into the knowledge surface
- Supervisor agent excluded from agentic culture (`enable_agentic_culture` not supported on Agno Team objects)
- Workshop queue not yet connected to any agent's tool surface (infrastructure ready, no agent uses it)
