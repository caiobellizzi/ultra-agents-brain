# Plan: `/gsd:map-codebase` — ultra-agents-brain

## Context

The `ultra-agents-brain` project has no `.planning/` directory yet. Before running `/gsd:new-project` or `/gsd:plan-phase`, a codebase map is needed to give GSD agents accurate structural context about the existing Python package, infrastructure, and skills layout.

This plan executes the `map-codebase` workflow to produce 7 structured reference documents in `.planning/codebase/`.

## Project State (confirmed by exploration)

- **No `.planning/` directory exists** — fresh start, no refresh prompt needed
- **Primary language:** Python (`ultra_brain/` package with ~13 modules)
- **Infrastructure:** Docker Compose, LiteLLM (model gateway), Hermes (Telegram bot), systemd/cron on VPS
- **Key directories:** `ultra_brain/`, `skills/`, `deploy/`, `vault/`, `scripts/`, `tests/`, `taks/`, `docs/runbooks/`

## Steps

### 1. Load init context
```bash
INIT=$(gsd-sdk query init.map-codebase)
AGENT_SKILLS_MAPPER=$(gsd-sdk query agent-skills gsd-codebase-mapper)
```
Extract: `mapper_model`, `commit_docs`, `codebase_dir`, `subagent_timeout`, `date`.

### 2. Create directory
```bash
mkdir -p .planning/codebase
```

### 3. Spawn 4 parallel `gsd-codebase-mapper` agents (background)

| Agent | Focus | Outputs |
|-------|-------|---------|
| 1 | tech | `STACK.md`, `INTEGRATIONS.md` |
| 2 | arch | `ARCHITECTURE.md`, `STRUCTURE.md` |
| 3 | quality | `CONVENTIONS.md`, `TESTING.md` |
| 4 | concerns | `CONCERNS.md` |

All agents use `run_in_background=true` and write directly to `.planning/codebase/`.

### 4. Collect confirmations & verify
```bash
ls -la .planning/codebase/
wc -l .planning/codebase/*.md
```
Confirm all 7 documents exist with non-zero line counts.

### 5. Commit (if `commit_docs` is true)
Conventional commit: `chore: add codebase map to .planning/codebase/`

## Verification

- [ ] `.planning/codebase/` exists with exactly 7 `.md` files
- [ ] Each document is non-empty and covers its focus area
- [ ] No agent errors in output

## Next Steps After Completion

```
/gsd:new-project   — initialize project with roadmap
/gsd:plan-phase 1  — plan first phase directly
```
