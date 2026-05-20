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
| T-01 | Tampering | Telegram HITL | Callback_data forged: run_id/agent_id/tool_call_id injected by attacker | mitigate | OPEN |
| T-02 | Tampering | vault.py | _impl functions bypassed — tool called directly, skipping assert_safe | accept | CLOSED (accept) |
| T-03 | Tampering | model.py | Hardcoded fallback LiteLLM key `sk-dev-local` ships to production | mitigate | OPEN |
| R-01 | Repudiation | AgentOS | No structured audit log of agent run requests or tool executions | accept | OPEN — not logged |
| I-01 | Info Disclosure | model.py | LiteLLM master key falls back to hardcoded `sk-dev-local` if env var unset | mitigate | OPEN |
| I-02 | Info Disclosure | systemd | Services run as root — vault + secrets accessible if process is compromised | accept | OPEN — not logged |
| I-03 | Info Disclosure | .env.example | API keys documented as empty strings; .env excluded via .gitignore | mitigate | CLOSED |
| D-01 | Denial of Service | AgentOS | Unauthenticated POST /agents/{id}/runs from localhost, no rate limit | accept | OPEN — not logged |
| D-02 | Denial of Service | LITELLM cost cap | DAILY_COST_CAP_USD env var exists but enforcement is LiteLLM-side | transfer | CLOSED |
| E-01 | Elevation of Privilege | systemd | uab-brain + uab-telegram run as root (no User= in service files) | mitigate | OPEN |
| E-02 | Elevation of Privilege | Telegram adapter | Empty TELEGRAM_ALLOWED_CHAT_IDS silently opens bot to all Telegram users | mitigate | OPEN |
| E-03 | Elevation of Privilege | HITL callback | agent_id from callback_data interpolated into URL without validation — path traversal possible | mitigate | OPEN |
| E-04 | Elevation of Privilege | AgentOS CORS | cors_allowed_origins includes http://localhost:3000 (any local process can call it from browser) | accept | CLOSED (accept, personal VPS) |

---

## Detailed Verification Evidence

### CLOSED threats

**S-01 / S-02 — Telegram allowlist (messages + callbacks)**
Both code paths check `ALLOWED_CHAT_IDS` before processing:
- Messages: `telegram_adapter.py:372` — `if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS`
- Callbacks: `telegram_adapter.py:355` — same guard on `chat_id` extracted from `query["message"]["chat"]["id"]`
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

### OPEN threats (BLOCKERs for high/critical)

---

**T-01 — BLOCKER (HIGH): Callback_data forged / run_id path injection**

`telegram_adapter.py:257`: `action, run_id, agent_id, tool_call_id = parts` — all four fields come from `callback_data` which is a Telegram-provided string. Telegram does not sign callback_data; any entity with a copy of the message can replay a forged callback with a crafted `agent_id` or `run_id`.

`telegram_adapter.py:286`: `continue_url = f"{AGENTOS_BASE_URL}/agents/{agent_id}/runs/{run_id}/continue"` — `agent_id` and `run_id` are interpolated directly into a URL path with zero validation. A crafted `agent_id` of `chat/../../etc` or similar could reach unintended AgentOS endpoints (SSRF-within-localhost).

No validation present. No grep match found for `validate`, `sanitize`, or allowlist check on `agent_id` after extraction from `callback_data`.

**Recommended mitigation:** Validate `agent_id` against a fixed allowlist (`{"chat", "ingest", "query", "research", "curator"}`) and validate `run_id` matches the UUID format before URL interpolation. Also verify `run_id` exists in `_PAUSED_TOOLS` before accepting any action on it.

---

**E-01 / I-02 — BLOCKER (HIGH): systemd services run as root**

Neither `uab-brain.service` nor `uab-telegram.service` contains a `User=` directive. On a standard Linux system, services without `User=` run as root. Verified: grep for `User=`, `Group=`, `DynamicUser`, `NoNewPrivileges` returned 0 matches in both service files.

This means a compromised agent process (e.g., via prompt injection into vault content) has full root access to the VPS, the vault, and all secrets in `.env`.

**Recommended mitigation:** Add `User=uabrain` (or similar non-root user), `NoNewPrivileges=true`, `PrivateTmp=true`, and `ReadWritePaths=/srv/second-brain` to both service files. The `.env.example` already references `UAB_SERVICE_USER=uabrain`.

---

**E-02 — BLOCKER (HIGH): Empty allowlist silently opens bot to all Telegram users**

`telegram_adapter.py:47-51`: if `TELEGRAM_ALLOWED_CHAT_IDS` is unset or empty string, `ALLOWED_CHAT_IDS` is an empty set. The guard at lines 355 and 372 is `if ALLOWED_CHAT_IDS and ...` — when the set is empty/falsy, the condition short-circuits and NO filtering occurs. The startup log at line 328 warns `"ALL (warning: open)"` but does not fail.

If the env var is accidentally left blank in production `.env`, the bot is fully open to any Telegram user who discovers the bot username. They can trigger `ingest` and `research` runs (with HITL prompts appearing in the operator's chat, but still a DoS vector).

**Recommended mitigation:** Fail-fast at startup: if `ALLOWED_CHAT_IDS` is empty, either `sys.exit(1)` with an explicit error or require an explicit `TELEGRAM_OPEN_TO_ALL=true` opt-in flag.

---

**T-03 / I-01 — BLOCKER (MEDIUM-elevated): Hardcoded LiteLLM key fallback**

`agentos/model.py:10`: `LITELLM_API_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-dev-local")`

The fallback `"sk-dev-local"` ships in production if `LITELLM_MASTER_KEY` is not set. If LiteLLM's master key is not configured, the proxy accepts any caller using `sk-dev-local`. This is a known-bad default that makes the LiteLLM proxy unauthenticated.

**Recommended mitigation:** Remove the fallback — raise at import time if `LITELLM_MASTER_KEY` is not set: `os.environ["LITELLM_MASTER_KEY"]` (KeyError on missing). Or at minimum validate it is not the dev placeholder on startup.

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
| CLOSED | 7 |
| OPEN (blocker) | 5 |
| Accepted (documented) | 4 |

**Blockers preventing ship:**
1. T-01 — No validation of agent_id/run_id from Telegram callback_data (URL injection)
2. E-01/I-02 — systemd services run as root
3. E-02 — Empty allowlist silently opens bot to all Telegram users
4. T-03/I-01 — Hardcoded LiteLLM key fallback `sk-dev-local` in production code
