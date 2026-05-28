# Plan — Seed vault with BASB + Karpathy gist; wire up Obsidian Web Clipper

## Context

The Phase 1 vault deployed to `/srv/second-brain` on the VPS is empty (only the
PARA scaffold exists). Two needs:

1. **Seed the vault with foundational reference material.** Tiago Forte's BASB
   overview and Karpathy's gist are the conceptual underpinning of how this
   second brain is supposed to be used. They belong in the vault as the first
   real notes — both so the agents have something to retrieve, and so future
   `query_vault` calls about "how should I organise X" return grounded
   answers.

2. **Make web clipping a first-class input channel.** Telegram `/ingest <url>`
   is fine for ad-hoc URLs but not for the natural "I'm reading something
   interesting" reflex. The Obsidian Web Clipper extension is the missing
   browser-side primitive. Decision: clip locally on the Mac into the existing
   `vault/` folder, then rsync to the VPS so the agents see new clips.

This plan also acts as the post-Wave-4 smoke test for the vault-path fix
(commit just landed: `SECOND_BRAIN_DIR` fallback in `agentos/tools/vault.py`).

---

## Step 1 — Manual URL ingest via Telegram (smoke test + seed)

No code changes. Just exercises the existing pipeline end-to-end on the VPS.

**URLs to ingest:**
- `https://fortelabs.com/blog/basboverview/`
- `https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f`

**Extraction path (reference, already in place):**
- `ultra_brain/ingest.py:60-90` — `Extractor._extract_url` tries
  `crawl4ai_endpoint` first, falls back to Jina Reader
  (`https://r.jina.ai/<url>`), then a placeholder note.
- VPS `.env` has no `CRAWL4AI_ENDPOINT`, so both URLs will land via Jina
  Reader. Jina handles plain blog pages and GitHub gists fine without auth.

**PARA placement (reference):**
- `ultra_brain/ingest.py:178-202` — `Filer._choose_tier` calls the LLM with
  title + first 500 chars and accepts only `00-Projects | 01-Areas |
  02-Resources | Inbox`. URLs with a clear "reference" tone heuristically
  fall back to `02-Resources` → `02-Resources/articles/`.
- Expected output paths:
  `/srv/second-brain/02-Resources/articles/2026-05-19-basboverview.md`
  `/srv/second-brain/02-Resources/articles/2026-05-19-llm-os-or-similar-slug.md`

**Procedure:**
1. In Telegram, send: `/ingest https://fortelabs.com/blog/basboverview/`
2. Tap **Approve** when the HITL card appears.
3. Repeat for the Karpathy gist URL.
4. SSH to VPS and confirm both files exist under
   `/srv/second-brain/02-Resources/articles/`.

---

## Step 2 — Obsidian local vault setup

Goal: make Obsidian on the Mac treat the project's `vault/` folder as a
first-class Obsidian vault so Web Clipper has somewhere to write.

**Files involved:**
- Existing folder: `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/vault/`
  (already mirrors the VPS PARA structure: `00-Projects`, `01-Areas`,
  `02-Resources`, `03-Archives`, `Inbox`, `_system`).
- `.gitignore` rule at the vault layer already excludes `YYYY-MM-DD-slug.md`
  ingested notes (commit `91563c3`), so clipper-generated notes will not
  pollute git.

**Steps (manual, no code):**
1. Install Obsidian (if not already).
2. *Open folder as vault* → pick `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/vault/`.
3. In Obsidian settings → *Files & links* → set *Default location for new
   notes* = `02-Resources/articles`.
4. Confirm `_system/schemas/note.frontmatter.json` is respected by any
   frontmatter plugin (already present).

---

## Step 3 — Obsidian Web Clipper config

Install the official extension
(`https://obsidian.md/clipper`) and configure it to match the existing
ingest-note shape so clips look identical to `ingest_to_vault` output.

**Settings:**
- *Vault*: the vault opened in Step 2.
- *Default folder*: `02-Resources/articles`.
- *Note name template*: `{{date}}-{{title|slug}}`  → produces
  `2026-05-19-some-article.md` (matches the `YYYY-MM-DD-slug.md` convention
  the .gitignore already filters on).
- *Properties / frontmatter*: include `source`, `clipped`, `tags` (mirrors
  the schema in `vault/_system/schemas/note.frontmatter.json`).
- *Body*: use the default "Article" template (extracts main content via
  Readability, drops nav/ads).

No code changes required — this is pure browser-extension config.

---

## Step 4 — Mac → VPS sync

One-way push: anything new under the local `vault/` lands on `/srv/second-brain/`
within a few minutes so the AgentOS query/digest/review/poll agents can see
new clips.

**Recommended approach: launchd + rsync.**

**Files to create:**
- `ops/sync-vault-to-vps.sh` (project, ~15 lines):
  ```sh
  #!/usr/bin/env bash
  set -euo pipefail
  rsync -av --update \
    --exclude '.obsidian/' \
    --exclude '.trash/' \
    --exclude '_system/log.md' \
    --exclude '_system/lint-report.md' \
    /Users/caiobellizzi/Documents/Projects/ultra-agents-brain/vault/ \
    root@31.97.130.253:/srv/second-brain/
  ```
- `ops/com.ultraagents.vault-sync.plist` (LaunchAgent, runs every 5 min):
  invokes the shell script above, logs to `/tmp/uab-vault-sync.log`.

**Install steps:**
- `cp ops/com.ultraagents.vault-sync.plist ~/Library/LaunchAgents/`
- `launchctl load ~/Library/LaunchAgents/com.ultraagents.vault-sync.plist`

**Why `--update` not `--delete`:** preserves notes that were created on the
VPS side (e.g. by the ingest agent or curator timers) and only adds new/changed
files from the Mac. Avoids accidental wipe.

**Why `--exclude '.obsidian/'`:** Obsidian's workspace state, plugins,
themes — irrelevant to the VPS-side agents and noisy in sync.

---

## Verification

End-to-end checks:

1. **Telegram ingests land in the right path.** On VPS:
   `ls /srv/second-brain/02-Resources/articles/ | grep -E 'basboverview|llm|karpathy'`
   → two new `.md` files dated today.

2. **Web Clipper round-trip.** Clip any test page → file appears at
   `~/Documents/Projects/ultra-agents-brain/vault/02-Resources/articles/YYYY-MM-DD-slug.md`
   within seconds.

3. **Sync round-trip.** Wait ≤5 min after a clip → SSH and confirm same file
   at `/srv/second-brain/02-Resources/articles/YYYY-MM-DD-slug.md` on VPS.

4. **Query agent sees the clipped content.** In Telegram:
   `/chat what do I know about PARA method` → reply cites
   `basboverview.md` with a line-range reference.

5. **No git pollution.** `git status` shows clipper notes untracked but
   excluded by the existing `.gitignore` rule for `YYYY-MM-DD-*.md`.

---

## Out of scope

- HTTPS exposure of AgentOS or a `/clip` HTTP endpoint (decided against —
  local vault + sync is simpler).
- Obsidian Sync (paid; not needed for one-way push).
- Reverse-sync from VPS → Mac (would need conflict resolution; punt until
  there's a real need, e.g. wanting to read agent-generated digest notes in
  Obsidian on the Mac — easy follow-up if it becomes useful).
- Automated tagging / PARA reclassification of clipper-imported notes by
  the curator agent (future enhancement; current behaviour: clipper picks
  the folder, curator just lints).

---

## Critical files

| Path | Change |
|------|--------|
| `ops/sync-vault-to-vps.sh` | NEW — rsync wrapper |
| `ops/com.ultraagents.vault-sync.plist` | NEW — LaunchAgent for 5-min schedule |
| `vault/` (existing) | No edit; used as the Obsidian vault root |
| `agentos/tools/vault.py:21` | No edit (fix already shipped) |
| `ultra_brain/ingest.py:60-90,178-202` | No edit; reference only |
