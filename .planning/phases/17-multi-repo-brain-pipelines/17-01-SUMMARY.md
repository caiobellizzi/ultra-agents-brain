---
plan: "17-01"
phase: "17-multi-repo-brain-pipelines"
status: complete
completed: 2026-05-27
---

# Summary — 17-01: Multi-Repo Brain Pipelines

## What Was Built

Replaced the defunct `reindex_bridge.sh` vault-write (raw stats JSON) with a proper CI-driven LLM prose summary pipeline. Each enrolled repo now generates a nightly `repos/<name>.md` in the second-brain vault via GitHub Actions + NVIDIA NIM.

## Artifacts Delivered

**Local (ultra-agents-brain):**
- `scripts/reindex_bridge.sh` — vault-write block (Steps 3+4) removed; codebase-memory-mcp reindex calls preserved
- `ops/sync-vault-to-vps.sh` — `--exclude 'repos/'` added to rsync EXCLUDES array
- `.github/workflows/summary.yml` — 5-line caller stub wiring to `brain-pipelines@v1`

**External:**
- `caiobellizzi/brain-pipelines` — new public repo with `generate-summary.yml` reusable workflow (Python-based NIM call, 24KB context cap, `GITHUB_REPOSITORY` for correct link URLs)
- `caiobellizzi/second-brain/.github/workflows/aggregate.yml` — fan-in workflow at 04:00 UTC downloading all `summary-*` artifacts and committing as `repos/*.md`
- `NVIDIA_NIM_API_KEY` secret wired in both `ultra-agents-brain` and `brain-pipelines`

## Smoke Verification

- Pipeline ran end-to-end: Actions → NIM (llama-3.3-70b-instruct) → artifact → `repos/ultra-agents-brain.md` in vault ✓
- Content: real prose summary with correct `https://github.com/caiobellizzi/ultra-agents-brain` base URLs (after fix) ✓
- rsync exclusion confirmed working ✓
- Telegram `/search` blocked by pre-existing Groq routing bug (filed as follow-up) — not introduced by this phase

## Deviations

- Two fixes to `brain-pipelines/generate-summary.yml` were required post-initial-deploy:
  1. `curl` → Python `urllib` (shell arg-list-too-long on large context)
  2. `github.event.repository.name` → `github.repository` (LLM was generating placeholder `user/` URLs)
- `brain-pipelines` default branch is `master`, not `main`

## Self-Check: PASSED
