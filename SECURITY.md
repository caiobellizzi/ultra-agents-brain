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
