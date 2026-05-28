---
phase: 17
slug: multi-repo-brain-pipelines
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 17 — Validation Strategy

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash (shell syntax checks) + pytest (integration, manual) |
| **Config file** | none — Wave 0 installs nothing (shell-only changes) |
| **Quick run command** | `bash -n reindex_bridge.sh && bash -n ops/sync-vault-to-vps.sh` |
| **Full suite command** | `bash -n reindex_bridge.sh && bash -n ops/sync-vault-to-vps.sh && python3 -c "import yaml; yaml.safe_load(open('.github/workflows/summary.yml'))"` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After Wave 1:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green + smoke test passed

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Automated Command | Status |
|---------|------|------|-------------|-------------------|--------|
| 17-01-T1 | 01 | 1 | BRAIN-04 | `bash -n reindex_bridge.sh && ! grep -q "vault/repos" reindex_bridge.sh` | ⬜ pending |
| 17-01-T2 | 01 | 1 | BRAIN-03 | `bash -n ops/sync-vault-to-vps.sh && grep -q "exclude.*repos" ops/sync-vault-to-vps.sh` | ⬜ pending |
| 17-01-T3 | 01 | 1 | BRAIN-01 | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/summary.yml'))"` | ⬜ pending |
| 17-01-CA | 01 | 2 | BRAIN-01 | manual — gh workflow list --repo caiobellizzi/brain-pipelines | ⬜ pending |
| 17-01-CB | 01 | 2 | BRAIN-02 | manual — gh workflow list --repo caiobellizzi/second-brain | ⬜ pending |
| 17-01-CC | 01 | 2 | BRAIN-01 | manual — gh secret list --repo caiobellizzi/ultra-agents-brain | ⬜ pending |
| 17-01-D  | 01 | 3 | BRAIN-01..05 | manual smoke (see plan checkpoint D) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No new test infrastructure needed — all automated verifications are shell one-liners run inline.

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| brain-pipelines SUMMARY.md artifact produced | BRAIN-01 | Requires external repo + GitHub Actions runtime | gh workflow run + gh run watch |
| second-brain repos/*.md written after fan-in | BRAIN-02 | Requires aggregate.yml in external repo | gh workflow run aggregate.yml + check file contents |
| VPS receives repos/*.md via git pull | BRAIN-03 | Requires SSH to VPS | git -C /srv/second-brain pull && ls repos/ |
| Telegram returns prose for enrolled repos | BRAIN-05 | Requires running Telegram bot + vault indexed | /search ultra-agents-brain in Telegram |

---

## Validation Sign-Off

- [ ] All local tasks (T1–T3) have automated shell verify
- [ ] All external checkpoints documented with manual verification steps
- [ ] Smoke test (checkpoint D) covers all 5 BRAIN requirements end-to-end
- [ ] `nyquist_compliant: true` set in frontmatter after sign-off

**Approval:** pending
