---
phase: 01
slug: ultra-brain-agno
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-19
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Telegram → Adapter | Long-poll from Telegram API; user messages and callback_data enter the system | User text, callback payloads (action, run_id, agent_id, tool_call_id) |
| Adapter → AgentOS | HTTP POST to localhost:7000; only adapter crosses this boundary | Agent run requests, HITL continue/resolve payloads |
| AgentOS → Vault | Python calls to ultra_brain modules; vault reads and writes | Note content, file paths, query text |
| AgentOS → LiteLLM | HTTP to localhost:4000; model API calls | User queries, agent prompts |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| S-01 | Spoofing — message allowlist | telegram_adapter.py:372 | mitigate | `ALLOWED_CHAT_IDS` guard; fail-fast at startup if empty (E-02 fix) | closed |
| S-02 | Spoofing — callback allowlist | telegram_adapter.py:355 | mitigate | Same `ALLOWED_CHAT_IDS` guard on callback chat_id | closed |
| T-01 | Tampering — callback_data URL injection | telegram_adapter.py:257-286 | mitigate | agent_id allowlist + UUID regex on run_id before URL interpolation | closed |
| T-02 | Tampering — assert_safe bypass | agentos/tools/safety.py | accept | assert_safe called before every vault write; accepted single-user scope | closed |
| T-03 | Tampering/Info — LiteLLM key fallback | agentos/model.py:10 | mitigate | Removed `"sk-dev-local"` default; `os.environ["LITELLM_MASTER_KEY"]` raises KeyError at startup if unset | closed |
| I-01 | Info Disclosure — secrets in repo | .gitignore, .env.example | mitigate | `.env` gitignored; all `.env.example` values are empty strings | closed |
| D-01 | DoS — LLM cost runaway | LiteLLM proxy | transfer | `DAILY_COST_CAP_USD` enforced by LiteLLM; not in this codebase | closed |
| D-02 | DoS — AgentOS unauth surface | agentos/__main__.py | accept | Binds `127.0.0.1` only; accepted AR-01 | closed |
| E-01 | Elevation — services run as root | deploy/systemd/ | mitigate | `User=uabrain`, `NoNewPrivileges=true`, `PrivateTmp=true` added to both service files; user created on VPS | closed |
| E-02 | Elevation — empty allowlist opens bot | telegram_adapter.py:47-60 | mitigate | Startup raises `RuntimeError` if `ALLOWED_CHAT_IDS` empty and `TELEGRAM_OPEN_TO_ALL` not set | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | D-02 | AgentOS binds localhost only; no TLS needed for single-user personal VPS | caio | 2026-05-19 |
| AR-02 | CORS localhost:3000 | Personal VPS, single user; CORS header is developer convenience | caio | 2026-05-19 |
| AR-03 | T-02 (assert_safe) | assert_safe is belt-and-suspenders inside trust boundary; accepted for personal deployment | caio | 2026-05-19 |
| AR-04 | _RESOLVED_RUNS in-memory | Restart clears dedup set; duplicate callbacks possible but low-risk on personal bot | caio | 2026-05-19 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-19 | 10 | 10 | 0 | gsd-security-auditor (retroactive-STRIDE) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-19
