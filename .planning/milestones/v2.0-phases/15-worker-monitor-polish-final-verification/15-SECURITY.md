<!-- generated-by: gsd-doc-writer -->
# SECURITY.md — Phase 01: ultra-brain-agno

**Audit date:** 2026-05-19
**Mode:** retroactive-STRIDE (no formal threat model existed at plan time)
**ASVS Level:** 1
**Block on:** critical, high

---

## Threat Register

| Threat ID | STRIDE | Component | Description | Disposition | Status |
|-----------|--------|-----------|-------------|-------------|--------|
| S-01 | Spoofing | Telegram adapter | Message from non-allowlisted chat_id impersonates authorized user | mitigate | CLOSED |
| S-02 | Spoofing | Telegram adapter | Callback query (approve/deny button) from non-allowlisted chat_id | mitigate | CLOSED |
| S-03 | Spoofing | AgentOS HTTP | Unauthenticated POST to AgentOS localhost by any local process | accept | OPEN — not logged |
| T-01 | Tampering | Telegram HITL | Callback_data forged: run_id/agent_id/tool_call_id injected by attacker | mitigate | CLOSED |
| T-02 | Tampering | vault.py | _impl functions bypassed — tool called directly, skipping assert_safe | accept | CLOSED (accept) |
| T-03 | Tampering | model.py | Hardcoded fallback LiteLLM key `sk-dev-local` ships to production | mitigate | CLOSED |
| R-01 | Repudiation | AgentOS | No structured audit log of agent run requests or tool executions | accept | OPEN — not logged |
| I-01 | Info Disclosure | model.py | LiteLLM master key falls back to hardcoded `sk-dev-local` if env var unset | mitigate | CLOSED |
| I-02 | Info Disclosure | systemd | Services run as root — vault + secrets accessible if process is compromised | accept | CLOSED |
| I-03 | Info Disclosure | .env.example | API keys documented as empty strings; .env excluded via .gitignore | mitigate | CLOSED |
| D-01 | Denial of Service | AgentOS | Unauthenticated POST /agents/{id}/runs from localhost, no rate limit | accept | OPEN — not logged |
| D-02 | Denial of Service | LITELLM cost cap | DAILY_COST_CAP_USD env var exists but enforcement is LiteLLM-side | transfer | CLOSED |
| E-01 | Elevation of Privilege | systemd | uab-brain + uab-telegram run as root (no User= in service files) | mitigate | CLOSED |
| E-02 | Elevation of Privilege | Telegram adapter | Empty TELEGRAM_ALLOWED_CHAT_IDS silently opens bot to all Telegram users | mitigate | CLOSED |
| E-03 | Elevation of Privilege | HITL callback | agent_id from callback_data interpolated into URL without validation — path traversal possible | mitigate | OPEN |
| E-04 | Elevation of Privilege | AgentOS CORS | cors_allowed_origins includes http://localhost:3000 (any local process can call it from browser) | accept | CLOSED (accept, personal VPS) |

---

## Detailed Verification Evidence

### CLOSED threats

**S-01 / S-02 — Telegram allowlist (messages + callbacks)**
Both code paths check `ALLOWED_CHAT_IDS` before processing:
- Messages: `telegram_adapter.py:373` — `if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS`
- Callbacks: `telegram_adapter.py:390` — same guard on `chat_id` extracted from `query["message"]["chat"]["id"]`
- Status: CLOSED. Guard is present at both entry points.

**I-03 — .env secrets not committed**
`.gitignore:1` lists `.env`. All secret vars in `.env.example` are empty strings. CLOSED.

**D-02 — Cost cap transferred to LiteLLM**
`DAILY_COST_CAP_USD` env var exists. Cost enforcement is LiteLLM-side (transfer disposition). CLOSED.

**E-04 — localhost:3000 in CORS**
Personal single-user VPS. Risk accepted for developer dashboard use. CLOSED as accepted risk.

**T-02 — assert_safe bypass via direct _impl call**
`assert_safe` is called inside `_ingest_to_vault_impl` (vault.py:30) and `_research_topic_impl` (vault.py:49). The `@tool(requires_confirmation=True)` wrapper delegates to these impls. Any call path through the `@tool` wrapper executes `assert_safe`. Accepted as low residual risk (LLM cannot call `_impl` directly; only the decorated function is registered in Agent.tools). CLOSED.

---

### Previously OPEN threats — now CLOSED

---

**T-01 — FIXED: Callback_data forged / run_id path injection**

`telegram_adapter.py:265`: `action, run_id, agent_id, tool_call_id = parts` — all four fields come from `callback_data` which is a Telegram-provided string.

`telegram_adapter.py:304`: `continue_url = f"{AGENTOS_BASE_URL}/agents/{agent_id}/runs/{run_id}/continue"` — `agent_id` and `run_id` are now validated before URL interpolation.

Validation now present at lines 267-276 of `telegram_adapter.py`: `agent_id` is validated against a fixed allowlist and `run_id` is validated against UUID format before URL interpolation. CLOSED.

---

**E-01 / I-02 — FIXED: systemd services run as root**

`User=uabrain`, `Group=uabrain`, and `NoNewPrivileges=true` are now present in both `uab-brain.service` and `uab-telegram.service`. Services no longer run as root. CLOSED.

---

**E-02 — FIXED: Empty allowlist silently opens bot to all Telegram users**

Fail-fast added at lines 54-57 of `telegram_adapter.py`: if `ALLOWED_CHAT_IDS` is empty and `TELEGRAM_OPEN_TO_ALL` is unset, the process exits with an explicit error at startup. The bot can no longer accidentally be opened to all users by an empty env var. CLOSED.

---

**T-03 / I-01 — FIXED: Hardcoded LiteLLM key fallback**

`agentos/model.py:10`: now uses `os.environ["LITELLM_MASTER_KEY"]` with no fallback. Missing env var raises `KeyError` at import time. CLOSED.

---

**S-03 / D-01 / R-01 — ACCEPTED RISK (documented below)**

AgentOS has no auth layer on its localhost HTTP surface. Any local process on the VPS can POST to `/agents/{id}/runs`. This is accepted for Phase 1 given:
- AgentOS binds to `127.0.0.1` only (verified: `__main__.py:11`, systemd `AGENTOS_HOST=127.0.0.1`)
- The VPS is single-tenant
- No external port exposure

These are documented here as accepted risks for ASVS Level 1 / personal deployment scope.

---

## Accepted Risks Log

| Risk ID | Description | Accepted Because |
|---------|-------------|-----------------|
| AR-01 | AgentOS HTTP has no auth (localhost only) | Single-tenant VPS, 127.0.0.1 bind only, no internet exposure |
| AR-02 | No structured audit log of agent runs | ASVS L1 scope, personal deployment |
| AR-03 | cors_allowed_origins includes localhost:3000 | Developer dashboard access on personal machine |
| AR-04 | _RESOLVED_RUNS is in-memory only — lost on restart, allowing duplicate approvals after restart | Low-likelihood, single-user, restart is rare |

---

## Summary

| Metric | Count |
|--------|-------|
| Threats identified | 16 |
| CLOSED | 11 |
| OPEN (blocker) | 1 |
| Accepted (documented) | 4 |

**Remaining open blocker:**
1. E-03 — agent_id from callback_data interpolated into URL without validation — path traversal possible

**Previously resolved blockers (now CLOSED):**
1. T-01 — Validation of agent_id/run_id from Telegram callback_data added (lines 267-276)
2. E-01/I-02 — systemd services now run as uabrain (non-root) with NoNewPrivileges=true
3. E-02 — Fail-fast at startup if ALLOWED_CHAT_IDS empty and TELEGRAM_OPEN_TO_ALL unset
4. T-03/I-01 — Hardcoded LiteLLM key fallback removed; KeyError raised if env var unset


---

<!-- generated-by: gsd-security-auditor — Phase 15 -->
## Phase 15 Addendum — worker-monitor-polish-final-verification

**Audit date:** 2026-05-28
**Mode:** retroactive-STRIDE (no formal threat model existed at plan time)
**ASVS Level:** 1
**Block on:** critical, high

### Threat Register

| Threat ID | STRIDE | Component | Description | Disposition | Status |
|-----------|--------|-----------|-------------|-------------|--------|
| P15-T-01 | Tampering | brief.py `_read_inbox_items` | Path traversal: `vault_root` is caller-supplied; attacker controlling arg could redirect reads | accept | CLOSED (accept) |
| P15-T-02 | Tampering | brief.py `_read_inbox_items` | Filename injection in glob: date pattern derived from `date.today()`, never from untrusted input | mitigate | CLOSED |
| P15-I-01 | Info Disclosure | check_surfaces.py | DSN credentials may appear in psycopg2 OperationalError printed to stdout on connection failure | accept | CLOSED (accept) |
| P15-I-02 | Info Disclosure | check_surfaces.py | Row counts printed to stdout; no sensitive schema data exposed | accept | CLOSED (accept) |
| P15-I-03 | Info Disclosure | check_surfaces.py | `POSTGRES_DSN_*` passed to `psycopg2.connect()` but never printed in normal operation | mitigate | CLOSED |
| P15-T-03 | Tampering / SQL Injection | check_surfaces.py | Table names interpolated into SQL — originally f-string, fixed to `psycopg2.sql.Identifier` | mitigate | CLOSED |
| P15-D-01 | Denial of Service | check_surfaces.py | `psycopg2.connect()` has no explicit timeout; unresponsive DB blocks indefinitely | accept | CLOSED (accept) |
| P15-T-04 | Tampering | check_surfaces.py | DSN env var pointing at attacker-controlled DB produces misleading counts; script is read-only | accept | CLOSED (accept) |
| P15-I-04 | Info Disclosure | brief.py `daily_brief()` | `IndexError` on malformed URL in `split("/")[2]` exposes stack trace — fixed to `urlsplit().netloc` | mitigate | CLOSED |
| P15-R-01 | Repudiation | sync-vault-to-vps.sh | 15-02 added tests only; no change to script's existing audit surface | accept | CLOSED (accept) |

### Detailed Verification Evidence

**P15-T-02 — Filename injection in glob: CLOSED**
`brief.py:72`: `inbox_dir.glob(f"{check_day.isoformat()}-*.md")` — `check_day` is derived solely from `date.today()` arithmetic. No external string is interpolated into the glob pattern. No injection vector exists.
Evidence: `ultra_brain/brief.py:70-72`

**P15-I-03 — DSN not printed in normal path: CLOSED**
`check_surfaces.py:52`: `psycopg2.connect(conn_str)` — `conn_str` is never echoed. Error path at line 67 prints only `exc` (exception message) and `table_name` (agno library attribute or literal). DSN value is not emitted.
Evidence: `scripts/check_surfaces.py:52,62,67`

**P15-T-03 — SQL injection via table name: CLOSED**
Original f-string interpolation (`f"SELECT COUNT(*) FROM {table_name}"`) was identified as CR-01 and fixed in commit `7658a97`. Current implementation at `check_surfaces.py:54` uses `psycopg2.sql.SQL("SELECT COUNT(*) FROM {}").format(psycopg2.sql.Identifier(table_name))`. All table name values come from agno library attributes or string literals — none from untrusted external input.
Evidence: `scripts/check_surfaces.py:54` (commit `7658a97`)

**P15-I-04 — IndexError on malformed URL: CLOSED**
Original `item["url"].split("/")[2]` (IndexError on short/empty URLs) was identified as WR-03 and fixed in commit `2ec3749`. Current implementation at `brief.py:152-156` uses `urllib.parse.urlsplit(item["url"]).netloc` with a guard that excludes empty results. `urlsplit().netloc` never raises on malformed input.
Evidence: `ultra_brain/brief.py:152-156` (commit `2ec3749`)

**P15-T-01 — vault_root path traversal: CLOSED (accepted)**
`vault_root` is operator-supplied via CLI or cron. No web/API surface accepts it from an unauthenticated caller. Accepted for single-user operator-controlled tool.
Evidence: `ultra_brain/brief.py:64,142`

**P15-I-01 — DSN in psycopg2 exception text: CLOSED (accepted)**
psycopg2 `OperationalError` on connection failure may include DSN credentials in the exception message string printed at `check_surfaces.py:67`. Accepted: personal single-user VPS, no shared log aggregation, same trust level as the operator who set the env var.

**P15-D-01 — No connection timeout: CLOSED (accepted)**
`psycopg2.connect()` without `connect_timeout` blocks up to OS TCP timeout. Accepted: operator-invoked diagnostic tool, not a long-running service.

### New Accepted Risks (Phase 15)

| Risk ID | Description | Accepted Because |
|---------|-------------|-----------------|
| AR-05 | vault_root path traversal in _read_inbox_items | Operator-controlled CLI arg, no external input path |
| AR-06 | psycopg2 OperationalError may include DSN credentials in printed exception text | Personal single-user deployment, no shared log aggregation |
| AR-07 | psycopg2.connect() has no explicit timeout | Diagnostic tool only, operator-invoked, not an automated service |
| AR-08 | POSTGRES_DSN_* env var could point at attacker-controlled DB | Script is read-only (SELECT COUNT only), no writes performed |

### Phase 15 Summary

| Metric | Count |
|--------|-------|
| Threats identified | 10 |
| CLOSED — mitigated in code | 3 (P15-T-02, P15-I-03, P15-T-03, P15-I-04) |
| CLOSED — accepted risk | 6 (P15-T-01, P15-I-01, P15-I-02, P15-D-01, P15-T-04, P15-R-01) |
| OPEN (blocker) | 0 |

Phase 15 ships clean. All threats closed or documented as accepted risk.
