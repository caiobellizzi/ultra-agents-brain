# Phase 14: Approvals Surface Activation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 14-Approvals Surface Activation
**Areas discussed:** Canonical trigger path, State update contract, Tool argument visibility, Broken native HITL fallback

---

## Canonical Trigger Path

| Option | Description | Selected |
|--------|-------------|----------|
| Ingest fixture | Use `/ingest /tmp/uab-approval-smoke.md`; deterministic, fast, and exercises an existing `requires_confirmation=True` tool. | Yes |
| Research topic | Use `/research <topic>`; exercises another gated tool but costs more and is slower. | |
| Both required | Make ingest and research both phase gates; broadest coverage but heavier verification. | |

**User's choice:** "follow your recommendations"
**Notes:** Selected ingest fixture as the canonical smoke path; research remains optional secondary coverage.

---

## State Update Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Telegram bridge | Telegram callback resolves the native AgentOS approval row and continues the paused run. | Yes |
| Continue only | Keep current adapter behavior; simpler but likely leaves approval row status pending. | |
| UI resolve required | Also require UI-side resolution; broader than the Telegram-first phase goal. | |

**User's choice:** "follow your recommendations"
**Notes:** Agno source indicates row creation and run continuation are separate concerns. APPR-02 requires native row state to change, so the Telegram callback should bridge row resolution if continue alone does not.

---

## Tool Argument Visibility

| Option | Description | Selected |
|--------|-------------|----------|
| Native full args | Use Agno-native `tool_name` and `tool_args` as the UI/API source of truth. | Yes |
| Redacted args | Hide sensitive-looking values before display; safer but risks obscuring the reviewed action. | |
| Summary only | Show a project-side summary; easier to read but not enough for APPR-03 evidence. | |

**User's choice:** "follow your recommendations"
**Notes:** Smoke inputs must be non-sensitive. Logs should truncate or summarize args, but the native row should retain the underlying tool call fields for APPR-03.

---

## Broken Native HITL Fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Stop and reopen audit | If a real gated run creates no native row, escalate to `RC-hitl-write-broken`. | Yes |
| Build mirror writer | Create project-owned approval rows to populate UI; risks masking Agno breakage. | |
| Hybrid | Allow only native row-resolution bridging, not mirror row creation. | Yes |

**User's choice:** "follow your recommendations"
**Notes:** Native `ai.agno_approvals` remains the source of truth. Resolution bridging is allowed because it updates the native row required by APPR-02.

---

## the agent's Discretion

- Exact module name for approval instrumentation.
- Whether the Telegram bridge uses AgentOS HTTP endpoints or an internal helper.
- Exact OBS field ordering and truncation length.
- Whether optional `/research` coverage is included after ingest passes.

## Deferred Ideas

- Sensitive argument redaction for approval rows/logs across all gated tools.
- UI-side approval resolution as a supported operator workflow.
- Additional `/research` gated-tool smoke coverage.
