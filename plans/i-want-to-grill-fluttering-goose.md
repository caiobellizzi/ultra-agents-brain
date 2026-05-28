# Multi-Repo Second Brain: GitHub-Sourced Prose Summaries → Vault → Telegram

## Context

**The problem.** The `codebase-memory-mcp` projects graph (347 nodes, SQLite at `~/.cache/codebase-memory-mcp/*.db`) is **Mac-local**. When anything runs on the VPS — the Telegram bot, a future ultra-workshop agent — it can't read the graph. The existing bridge (`scripts/reindex_bridge.sh` → `vault/repos/<repo>/ARCHITECTURE.md`) only dumps **raw stats JSON**, which is useless as a reference.

**The real goal (clarified during grilling).** Not workshop plumbing. A **personal "second brain for all my code"**: ask from Telegram / anywhere — *"what does repo X do? how is it built? where did I leave off?"* — about **every** repo, not just local ones. Because a **team** can push, **GitHub is the source of truth**, so the pipeline must run server-side and be Mac-independent.

**The decision, grilled to ground.** Research (2025–26 state of the art) is unambiguous for a personal multi-repo brain queried a few times a day:
- **Don't** sync a full code graph to the VPS or rebuild it per-commit — over-built, and the from-anywhere questions are "what/why/status" prose, not call-graph traces.
- **Do** compile **per-repo prose summaries** (Karpathy "LLM wiki" / compiler pattern) into the vault, which **already** rsyncs to the VPS and is **already** BM25-searchable from Telegram.
- The local graph keeps its real job: **structural queries while coding at the Mac** (Claude Code). It is *not* an input to the prose layer (it's Mac-local and can't represent GitHub HEAD / teammates' pushes).

**Locked decisions (Q1–Q8):**
1. Audience = all repos, personal brain. (Q1)
2. Telegram queries are type-A "what/why/status" prose. Graph stays local. (Q2)
3. Summaries are **LLM-compiled** from `README` + `.planning/` + `git log` + file tree. (Q3)
4. Cadence = **nightly**, not per-commit LLM (no token tax for stable architecture facts). (Q4)
5. Compile venue = **GitHub Actions** (runs at the source of truth, team-aware, Mac-independent). (Q5)
6. Vault sync authority is **split**: rsync owns human notes, **git owns `repos/`**. (Q6)
7. Model = **NVIDIA NIM** (free 40 RPM tier) via a hosted API key as a CI secret. (Q7)
8. Schema defined below; **retire the vault-write half of `reindex_bridge.sh`** (local graph reindex stays). (Q8)
9. Enrollment is **opt-in** per repo → sensitive repos are simply not enrolled (honors the existing "local-only by privacy contract" principle).

---

## Architecture

```
owner/brain-pipelines  (NEW public repo — the template, ALL logic, tagged @v1)
   └ .github/workflows/llm-summary.yml   (on: workflow_call)
        checkout → gather README + .planning/* + `git log` + file tree
        → NIM LLM distill → commit SUMMARY.md back to the calling repo

each enrolled repo ×N   (caller stub planted once via multi-gitter)
   └ .github/workflows/summary.yml   (5 lines)
        on: { schedule: nightly, workflow_dispatch: {} }
        uses: owner/brain-pipelines/.github/workflows/llm-summary.yml@v1
        secrets: { NVIDIA_NIM_API_KEY }

owner/second-brain  (the vault repo — SINGLE writer to itself)
   └ .github/workflows/aggregate.yml   (staggered ~2h after source repos)
        for each enrolled repo: gh api .../contents/SUMMARY.md → repos/<name>.md
        commit + push   ("[skip ci]")

VPS  (always-on)
   └ cron: `git -C /srv/second-brain pull`   → repos/*.md land
   └ Telegram bot → existing BM25 vault search picks up repos/*.md

Mac
   └ cron: `git -C ~/Documents/second-brain pull`  (so Obsidian shows summaries)
   └ rsync EXCLUDES repos/  (git owns that subtree; no --delete fight)
```

**Version propagation (the "stay up to date" answer):**
- Pipeline logic updates → force-push floating `@v1` tag → all repos pick it up next nightly run, zero downstream edits.
- Breaking `@v1→@v2` → Renovate opens auto-merge PRs across caller stubs.
- Initial rollout / new repo → `multi-gitter` plants the stub + `gh secret set NVIDIA_NIM_API_KEY`.

---

## `repos/<name>.md` schema (the compiled summary)

```markdown
# <repo>
**Purpose:** one paragraph — what it is, who it's for
**Stack:** languages, key frameworks
**Architecture:** key modules and how they relate (prose, not a call graph)
**Status:** current milestone / what's in flight (from ROADMAP/PROJECT.md)
**Recent activity:** last ~7 days of commits, summarized
**Key decisions:** pointers to ADRs / locked plans
**Entry points:** where to start reading the code
**Links:** repo URL, vault project note
```
The LLM degrades gracefully when inputs are absent (not every repo has `.planning/`; `README` + `git log` + tree always exist).

---

## Work breakdown

### A. Central pipeline repo (new, lives outside ultra-agents-brain)
1. Create **public** `owner/brain-pipelines`.
2. `.github/workflows/llm-summary.yml` — `workflow_call`, input `repo_ref`, secret `NVIDIA_NIM_API_KEY`. Steps: checkout → a small script gathers inputs (cap token budget) → NIM chat completion (cheap model) → write `SUMMARY.md` → commit back with `[skip ci]`.
3. Tag `v1` (floating) + `v1.0.0` (pinned).

### B. Enrollment (one-time, per chosen repo)
4. Caller stub `.github/workflows/summary.yml` (nightly `schedule` + `workflow_dispatch`).
5. Roll out with `multi-gitter` over an explicit opt-in repo list; `gh secret set NVIDIA_NIM_API_KEY` per repo.
6. Add Renovate config so caller-stub version bumps auto-PR.

### C. Vault fan-in (in the `second-brain` repo)
7. `.github/workflows/aggregate.yml` — staggered nightly; read-only fine-grained PAT (`contents: read`) to fetch each repo's `SUMMARY.md` via `gh api`; write `repos/<name>.md`; commit as the sole writer.

### D. ultra-agents-brain repo changes (the only edits *here*)
8. `ops/sync-vault-to-vps.sh` — add `--exclude 'repos/'` to the `EXCLUDES` array (line 18–27) so rsync's `--delete` never touches the git-owned subtree.
9. `scripts/reindex_bridge.sh` — **remove the ARCHITECTURE.md vault-write block** (the `get_architecture` capture + `$VAULT_REPO_DIR/ARCHITECTURE.md` write). **Keep** the `detect_changes` / `index_repository` calls — the local graph stays hot for Claude Code. Update the header comment to reflect "local reindex only." Re-copy to `.git/hooks/post-commit`.
10. `deploy/cron/ultra-agents-brain.cron` — add a `git -C /srv/second-brain pull --ff-only` line (e.g. `*/10`), so VPS receives `repos/*.md`. Add the matching Mac-side pull (launchd or cron) for Obsidian.
11. Remove the now-stale `vault/repos/<repo>/ARCHITECTURE.md` stats files (one-time cleanup).
12. README / CONFIGURATION docs sync per the README-sync rule (new pipeline repo, new secret, sync-authority split).

---

## What is explicitly NOT built (anti-scope)
- No `codebase-memory-mcp` binary or `.db` files on the VPS.
- No per-commit LLM regeneration.
- No vector RAG / pgvector for this (research: over-built at ~10–20 repos).
- No second public LLM endpoint; NIM is called directly from CI.
- No structural/call-graph section in summaries (would force the graph into CI).
- Local graph and `reindex_bridge.sh`'s reindex call are **untouched** beyond dropping the vault write.

---

## Verification (end-to-end)
1. **Pipeline unit:** trigger `summary.yml` via `workflow_dispatch` on one enrolled repo → confirm a sensible `SUMMARY.md` is committed back; confirm NIM key consumed, cost ~negligible.
2. **Fan-in:** run `aggregate.yml` manually → confirm `repos/<name>.md` appears in `second-brain` with one clean commit, no conflicts when multiple repos are enrolled.
3. **Delivery:** on VPS, run the `git pull` → confirm `repos/<name>.md` present at `/srv/second-brain/repos/`.
4. **No rsync fight:** force a vault rsync cycle → confirm `repos/*.md` is **not** deleted (exclude works) and human notes still sync normally.
5. **Telegram:** query the bot for a repo by name → confirm BM25 returns the summary content.
6. **Bridge regression:** make a commit in `ultra-agents-brain` → confirm local graph reindexes (`detect_changes` runs) and **no** `ARCHITECTURE.md` is written to the vault.
7. **Propagation:** push a trivial change to `brain-pipelines`, force-push `@v1` → confirm an enrolled repo's next run uses the new logic with no stub edit.

---

## Open follow-ups (not blocking)
- Cross-repo `index.md` (all repos, one-line each) so "which repos touch Telegram?" is one BM25 hit.
- If laptop-independence ever matters for the *local graph* too: Tailscale-expose it (Aperture) rather than syncing `.db`.
