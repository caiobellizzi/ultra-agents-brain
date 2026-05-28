# GSD Import Plan: calm-whistling-tome.md → Phase 18

## Context

`plans/calm-whistling-tome.md` is a freeform design document capturing the Phase 18 plan for
automating the second-brain→VPS sync and pgvector reindex pipeline. Phase 17 built the nightly
`repos/*.md` summaries and the `aggregate.yml` workflow, but the files only reach pgvector via
manual scp+reindex. This import converts the freeform doc into a GSD PLAN.md and registers Phase
18 in the roadmap.

**Conflict detection result:** 0 BLOCKERs, 0 WARNINGs, 2 INFO (new phase addition, new script).
No gates to clear — proceeding directly to write.

---

## Step 1 — Create phase directory and write PLAN.md

Create: `.planning/phases/18-auto-sync-second-brain/18-01-PLAN.md`

Content:

```markdown
---
phase: "18-auto-sync-second-brain"
plan: "18-01"
type: "feature"
wave: 1
depends_on: ["17-01"]
files_modified:
  - "scripts/reindex-vault.sh"
  - "scripts/git-sync.sh"
autonomous: true
must_haves:
  truths:
    - "Phase 17 complete (2026-05-27): repos/*.md summaries land in second-brain via aggregate.yml"
    - "uabrain cron (5 min): git-sync.sh push && git-sync.sh pull on /srv/second-brain"
    - "second-brain repo is private: VPS HTTPS remote broken since making it private"
    - "POSTGRES_DSN_KNOWLEDGE must be sourced from .env or reindex silently no-ops"
    - "Reindex walk takes ~50s; flock guard required to prevent double-reindex on overlapping crons"
    - "/opt/ultra-agents-brain is NOT a git checkout — code ships via scp"
  artifacts:
    - "scripts/reindex-vault.sh exists, is executable, and flock-guards against double-run"
    - "scripts/git-sync.sh pull branch captures HEAD before/after and triggers reindex on .md change"
    - "VPS remote switched to SSH: git@github.com:caiobellizzi/second-brain.git"
    - "GitHub deploy key vps-uabrain registered (write-enabled) on caiobellizzi/second-brain"
    - "sudo -u uabrain git -C /srv/second-brain fetch origin main succeeds"
    - "End-to-end: .md commit on GitHub appears in pgvector within ~5 min, no manual action"
---

## Goal

Automate the pipeline: second-brain commit → VPS pull → pgvector reindex, so repos/*.md summaries
produced by Phase 17 are queryable from Telegram within ~5 minutes of being committed to GitHub,
with no manual intervention.

## Tasks

### Part A — Restore VPS↔GitHub auth (SSH deploy key)

Prerequisite. The 5-min cron is currently failing because second-brain is private and the VPS
remote uses anonymous HTTPS.

- [ ] A1: On VPS, generate ed25519 keypair as uabrain:
      `sudo -u uabrain ssh-keygen -t ed25519 -f /home/uabrain/.ssh/second_brain_deploy -N ""`
      Create ~/.ssh with 700 permissions if missing.
- [ ] A2: Configure /home/uabrain/.ssh/config to use the key for github.com:
      ```
      Host github.com
        IdentityFile ~/.ssh/second_brain_deploy
        IdentitiesOnly yes
      ```
      chmod 600 the config. Add github.com to known_hosts:
      `sudo -u uabrain ssh-keyscan github.com >> /home/uabrain/.ssh/known_hosts`
- [ ] A3: Register the public key as write-enabled deploy key via gh:
      `gh repo deploy-key add <pubkey> --repo caiobellizzi/second-brain --title vps-uabrain --allow-write`
- [ ] A4: Switch VPS remote from HTTPS to SSH:
      `sudo -u uabrain git -C /srv/second-brain remote set-url origin git@github.com:caiobellizzi/second-brain.git`
- [ ] A5: Verify pull and push auth as uabrain.

### Part B — Reindex helper script (new, version-controlled)

New file: `scripts/reindex-vault.sh`

- [ ] B1: Write scripts/reindex-vault.sh with:
      - flock -n on /tmp/uab-reindex.lock (log "another reindex in progress; skipping" and exit 0 if locked)
      - source /opt/ultra-agents-brain/.env (provides POSTGRES_DSN_KNOWLEDGE)
      - APP_DIR="${APP_DIR:-/opt/ultra-agents-brain}"
      - Run "$APP_DIR/.venv/bin/python" -m agentos.knowledge --reindex
      - Log to /opt/ultra-agents-brain/logs/reindex.log with timestamps
      - Always exit 0 (reindex failure must not break git-sync cron)
      - chmod +x

### Part C — Trigger reindex from git-sync.sh pull branch

Edit `scripts/git-sync.sh`, pull branch only. Current pull branch does a bare fetch + ff-only merge.

- [ ] C1: Capture HEAD before merge, run merge, capture HEAD after, then:
      ```bash
      pull)
        git fetch "$REMOTE" "$BRANCH" --quiet
        BEFORE=$(git rev-parse HEAD)
        git merge --ff-only "$REMOTE/$BRANCH" --quiet || {
          echo "git-sync: fast-forward failed; manual merge required" >&2
          exit 1
        }
        AFTER=$(git rev-parse HEAD)
        if [ "$BEFORE" != "$AFTER" ] && git diff --name-only "$BEFORE" "$AFTER" | grep -q '\.md$'; then
          "$(dirname "$0")/reindex-vault.sh" || true
        fi
        ;;
      ```
      push branch unchanged.

### Part D — Deploy to VPS

- [ ] D1: scp scripts/git-sync.sh root@31.97.130.253:/opt/ultra-agents-brain/scripts/git-sync.sh
- [ ] D2: scp scripts/reindex-vault.sh root@31.97.130.253:/opt/ultra-agents-brain/scripts/reindex-vault.sh
- [ ] D3: ssh to set permissions and create logs dir:
      `chmod +x /opt/ultra-agents-brain/scripts/reindex-vault.sh`
      `mkdir -p /opt/ultra-agents-brain/logs && chown uabrain /opt/ultra-agents-brain/logs`

No service restart needed — cron picks up new scripts on next tick.

## Verification

1. **Auth restored:** `sudo -u uabrain git -C /srv/second-brain fetch origin main` succeeds.
2. **Reindex fires on .md change:** force a repos/*.md change, run git-sync.sh pull, confirm reindex.log shows fresh index entry.
3. **No reindex on no-op:** second pull with nothing new — helper not invoked, no new log entry.
4. **Concurrency guard:** while reindex running, second reindex-vault.sh logs "skipping" and exits 0.
5. **Live query:** curl the query endpoint with a term unique to a newly-synced file; confirm answer cites repos/<name>.md (use fresh session_id).
6. **Full cron loop:** let cron run unattended; GitHub repos/ change appears in pgvector within ~5 min.
```

---

## Step 2 — Update ROADMAP.md

Add Phase 18 to the v2.6 milestone section (after Phase 17 entry). Insert:

```markdown
### 📋 v2.6 Phase 18: Auto-sync second-brain → VPS + pgvector reindex

**Goal:** Automate the pipeline so second-brain repo commits reach pgvector within ~5 min with
no manual scp/reindex.

**Plans:** 18-01

**Gate:** Begin after Phase 17 verified complete. ✅ Phase 17 complete 2026-05-27.
```

Also add Phase 18 row to the v2.6 milestone table:

```
| 18 | Auto-sync VPS + pgvector | second-brain commits land in pgvector within 5 min automatically | SYNC-01 |
```

---

## Verification

After writing both files:
- `.planning/phases/18-auto-sync-second-brain/18-01-PLAN.md` exists with valid frontmatter
- ROADMAP.md lists Phase 18 under v2.6
- Delegate validation to `gsd-plan-checker`

---

## Files to create/modify

| File | Action |
|------|--------|
| `.planning/phases/18-auto-sync-second-brain/18-01-PLAN.md` | CREATE |
| `.planning/ROADMAP.md` | EDIT — add Phase 18 to v2.6 section |
