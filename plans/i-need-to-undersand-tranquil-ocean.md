# Understanding the Second-Brain Architecture

## Context

The user asked three connected questions about where the second brain actually lives:
1. Does `ultra-agents-brain/vault/` reflect the VPS vault?
2. Shouldn't the second brain be a separate repo from the agents code?
3. Is `~/Documents/second-brain` a copy of the VPS vault, or a separate git project?

This document captures the **observed reality** of the setup so the user can decide whether anything actually needs to change.

---

## The current architecture (observed, not proposed)

There are **three physical copies** of the vault and **one canonical source of truth**:

```
                       ┌──────────────────────────────────────┐
                       │  GitHub: caiobellizzi/second-brain   │  ← canonical
                       │         (private repo)               │
                       └──────────────────────────────────────┘
                          ▲                            ▲
                          │ git push/pull              │ git push/pull
                          │ (manual + auto-sync hooks) │ (cron: scripts/git-sync.sh)
                          │                            │
            ┌─────────────┴─────────────┐  ┌──────────┴──────────┐
            │ Mac: ~/Documents/         │  │ VPS: /srv/           │
            │      second-brain         │  │      second-brain    │
            │      (working copy)       │  │      (working copy)  │
            └─────────────┬─────────────┘  └──────────────────────┘
                          ▲
                          │ symlink (gitignored)
                          │
            ┌─────────────┴─────────────────────────────┐
            │ ultra-agents-brain/vault → ~/Documents/   │
            │                          second-brain     │
            └────────────────────────────────────────────┘
```

### Concrete facts verified
- **`~/Documents/second-brain/.git`** → `origin = git@github.com:caiobellizzi/second-brain.git`. Independent git project. Most recent commit: `ba53eb7 vault: auto-sync 2026-05-21 14:51:17`.
- **`ultra-agents-brain/vault`** → symlink to `/Users/caiobellizzi/Documents/second-brain`. Listed in `.gitignore` line 17. Not tracked by the agents repo.
- **VPS `/srv/second-brain`** → clone of the same GitHub repo. `scripts/git-sync.sh` runs `pull` before writes and `push` after writes against `origin/main` (env var `VAULT_VPS_PATH`).
- **Deploy config** points the agentos service at `/srv/second-brain` via `SECOND_BRAIN_DIR` env var (`deploy/docker-compose.yml`, `deploy/systemd/uab-brain.service`, all cron entries).

### Answers to the three questions

| Question | Answer |
|---|---|
| Does `vault/` in the agents repo reflect the VPS vault? | **Indirectly.** Both Mac (`~/Documents/second-brain`) and VPS (`/srv/second-brain`) are independent clones of the same GitHub repo `caiobellizzi/second-brain`. They converge through `git push`/`pull`, not via direct mirroring. `ultra-agents-brain/vault` is just a symlink to the Mac clone. |
| Should the second brain be a separate repo? | **It already is.** `caiobellizzi/second-brain` is a standalone private GitHub repo. The agents repo never contains vault content — it only contains a symlink, which is gitignored. |
| Is `~/Documents/second-brain` a copy of the VPS vault? | **Neither is a "copy of" the other.** Both are working copies of the same upstream (`github.com/caiobellizzi/second-brain`). GitHub is the source of truth; Mac and VPS are peers. |

---

## Resolution

User confirmed (2026-05-21): purpose was **verification only**. The architecture matches the intended design; **no changes required**. This document stands as a reference for the next time the question comes up.

### Mental model in one sentence
> GitHub `caiobellizzi/second-brain` is canonical. Mac and VPS are independent peer working copies that sync through GitHub. The `ultra-agents-brain/vault` symlink is a local-developer convenience that never leaks vault content into the agents repo.

---

## Verification (how to re-confirm any of this)

```bash
# Confirm the symlink and its target
ls -la ultra-agents-brain/vault

# Confirm the canonical repo identity
cd ~/Documents/second-brain && git remote -v && git log --oneline -3

# Confirm vault is gitignored in the agents repo
grep -n "^vault$" ultra-agents-brain/.gitignore

# Confirm VPS sync wiring
cat ultra-agents-brain/scripts/git-sync.sh
grep -rn "SECOND_BRAIN_DIR\|VAULT_VPS_PATH" ultra-agents-brain/deploy/
```
