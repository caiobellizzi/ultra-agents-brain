# BACKLOG.md — parked findings from phase 10 (diagnostic audit)

Carryover bugs, research-surfaced candidates, and audit-surfaced findings that did **not** get folded into phases 11–14 plans. **These items are parked. Operator review decides which (if any) get promoted to REQUIREMENTS.md.** Editing or pruning this list is the only action this phase asks of you after read-through.

## Items

| ID | Title | Severity | Suggested phase | Repro one-liner |
|---|---|---|---|---|
| MON-01 | worker.monitor date-mismatch causes daily-brief to miss filed items (S21808) | medium | phase 15 | Run `python -m ultra_brain.worker.monitor` and `python -m ultra_brain.daily_brief` on the same day; observe daily-brief reports zero new items despite monitor having filed N stubs into the inbox. |
| MON-02 | Vault sync `--delete` flag deletes VPS-generated inbox items (S21815) | high | phase 15 | Run `scripts/sync-vault.sh` (or whatever wrapper invokes `rsync --delete`) while VPS monitor has created new files local-side hasn't yet pulled; observe the just-filed inbox stubs disappear. Fixed once in S21815 but flagged for full audit. |
| DIAG-BL-01 | `agentos/app.py` does not pin `BaseDb.id` — every redeploy regenerates the UUID | high | phase 11 (precondition) | Restart `uab-brain.service`, then `curl http://31.97.130.253:7000/config` before and after; compare the `os_database` UUID field. Closed by Option A in `DB-ID-DECISION.md`. |
| DIAG-BL-02 | If `POSTGRES_DSN_SESSIONS` is unset, SqliteDb fallback may not implement approval methods → `/approvals` could 503 | medium | phase 14 | `unset POSTGRES_DSN_SESSIONS` locally, run `python -m agentos`, probe `GET /approvals`. Document the actual behavior. (Not exercised in production — the VPS has the DSN set.) |
| DIAG-BL-03 | No production eval harness — `agno_eval_runs` stays empty until a CI/cron driver explicitly invokes the write path | medium | phase 12 | `curl http://31.97.130.253:7000/eval-runs` on a fresh deployment; observe empty array. `evals/conftest.py` is pytest-only and does not exercise `db.create_eval_run`. |
| DIAG-BL-04 | Phase research assumed agent factories needed `enable_user_memories=True`; project actually uses `enable_agentic_memory=True` everywhere | low | phase 11 (correction) | `grep -rn "enable_user_memories" agentos/` returns zero matches; `grep -rn "enable_agentic_memory" agentos/` returns 6+ matches. The original DIAG-BL-04 framing in `10-RESEARCH.md` is wrong — memory is not "structurally disabled". Phase 11's flag-flip story is already done; what remains is the `BaseDb.id` pin (DIAG-BL-01). |

## Audit-surfaced section

The following items were not in `10-RESEARCH.md` but were surfaced during plan 10-01 execution. They are listed here for operator review:

| ID | Title | Severity | Suggested phase | Repro one-liner |
|---|---|---|---|---|
| DIAG-BL-05 | `agno_knowledge` Postgres database is provisioned but completely **unmigrated** — zero tables in both `public` and `ai` schemas | high | phase 13 | `ssh root@31.97.130.253 'sudo -u postgres psql -d agno_knowledge -c "\dt"'` → returns "Did not find any relations." `POSTGRES_DSN_KNOWLEDGE` is set in `.env` but no PgVector / agno schema migration has ever been run against that DSN. Without this, `RC-knowledge-not-registered` cannot be resolved. |
| DIAG-BL-06 | `VaultKnowledge` silently falls back to an empty stub when its DSN check fails; `/knowledge/config` then returns `Available IDs: []` despite `AgentOS(knowledge=[kb], …)` being called | high | phase 13 | `curl http://31.97.130.253:7000/knowledge/config` → HTTP 400 with `"Available IDs: []"`. Project comment at `agentos/app.py:53-54` confirms the silent fallback. Need to either make the fallback loud (raise / log warn) or fix the upstream init so the real `Knowledge` registers correctly. |
| DIAG-BL-07 | AgentOS runs as `systemd:uab-brain.service`, not via docker-compose — but `deploy/docker-compose.yml` still references an agentos service shape in some commands/docs | medium | phase 15 (docs) | `docker compose -f deploy/docker-compose.yml ps` lists only `deploy-litellm-1`. The diagnostic plan/research assumed `docker compose exec agentos`; this assumption is wrong. Reconcile docs, dev-mode compose, and prod systemd so future planners aren't misled. |
| DIAG-BL-08 | `GET /databases` returns HTTP 404 in agno 2.6.7; the endpoint isn't exposed (only `/databases/{db_id}/migrate` is) | low | phase 12 / docs | `curl -sS -w "%{http_code}\n" http://31.97.130.253:7000/databases` → 404. `10-RESEARCH.md` and 10-01-PLAN's Task 1 instruct the use of `GET /databases`; both should be updated to reference `GET /config` (which returns the `databases` array directly). |
| DIAG-BL-09 | AgentOS is **open** on the production VPS — `GET /memories`, `/eval-runs`, `/approvals`, etc. return 200 without any `Authorization` header | high | phase 15 (security) | `curl -sS http://31.97.130.253:7000/memories` (no auth) → HTTP 200, returns the workshop-user memory row including its `memory` content text. The plan/research assumed `Authorization: Bearer $AGENTOS_JWT` was required. If this exposure is intentional (e.g. firewalled at the network layer), document the rationale; if not, configure AgentOS auth. |
| DIAG-BL-10 | Agno tables live in the `ai` Postgres schema, not `public` — undocumented in project | low | docs | `psql -d agno_sessions -c "\dn"` shows schemas `ai` (owner uab) + `public` (empty). All 15 `agno_*` tables are in `ai`. The plan and most queries default-search `public` and fail with "relation does not exist". Document this schema choice (or its origin — likely an Agno default or `db_schema=` override during initial deploy). |

## Footer

These items are **not** requirements until the operator promotes them. Editing this file is the only action this phase asks of you after read-through. Promotion to `REQUIREMENTS.md` (with new `REQ-XX-YY` ids) is a deliberate, separate operator action — typically done at the start of the suggested phase plan, not in this diagnostic phase.
