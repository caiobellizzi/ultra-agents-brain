---
name: telos.check
description: Lightweight TELOS alignment scoring for medium-risk approval prompts and routing decisions.
---

# telos.check

## Purpose

Score whether a proposed medium-risk action aligns with TELOS. Return concise reasoning for approval prompts without making the decision automatically.

## Triggers

- Before medium-risk vault writes, archives, recurring feed additions, paid TTS generation, or research tasks above normal budget.
- User asks "does this align with TELOS?".
- Weekly review or monitor feed selection needs prioritization.

## Required Env/Config

- `_system/telos.md` and optional split files under `_system/telos/`.
- LiteLLM Tier C by default.
- Cost ledger/trust gate helper.
- Telegram approval prompt formatter.

## Expected Inputs

- `proposed_action`: action summary, target files, cost estimate, and reversibility.
- Optional `context`: user request, current Project/Area, recent review notes.

## Expected Outputs

- Alignment score from 0.0 to 1.0.
- `supports`: TELOS points that favor the action.
- `concerns`: TELOS points that argue against it.
- `approval_prompt`: concise human-facing approval text.
- Recommendation: approve, revise, defer, or refuse if high-risk policy applies.

## Cost/Trust Constraints

- Typical cost target USD 0.003-0.008.
- Never bypass the medium-risk approval gate.
- If TELOS is absent, return "not enough TELOS context" and use standard approval prompt.
- Private content follows the same Tier D/refusal rule as other skills.

## Relevant Helper Modules

- No dedicated module beyond the planned skill entrypoint.
- Approval prompt/trust helper from task 06.

## Failure Handling

- If TELOS files are missing, skip scoring and state that TELOS is not initialized.
- If action details are too vague, ask the orchestrator for cost, reversibility, and target path before scoring.
