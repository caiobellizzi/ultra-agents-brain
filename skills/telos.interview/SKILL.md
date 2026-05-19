---
name: telos.interview
description: Multi-session interview workflow that drafts and refines the user's TELOS identity and decision context over short sessions.
---

# telos.interview

## Purpose

Build TELOS without turning it into a blocking project. Run short interviews, ask 5-10 focused questions per session, maintain interview state, draft `_system/telos.md`, and later split stable sections into mission, quarter goals, values, and dont-do files.

## Triggers

- Telegram command `/interview`.
- User says "work on TELOS", "define my direction", "help me clarify goals", or "update TELOS".
- Weekly review recommends a TELOS refinement.

## Required Env/Config

- `SECOND_BRAIN_ROOT` with writable `_system/telos.md` and `_system/telos/`.
- Interview state helper.
- LiteLLM Tier A for synthesis.
- Cost ledger/trust gate helper.
- 30 minute/week TELOS time cap from the plan.

## Expected Inputs

- Optional `session_goal`: mission, goals, values, dont-do, feed interests, or review.
- Prior `_system/telos.md` if it exists.
- Prior interview transcript/state if it exists.
- User answers over Telegram.

## Expected Outputs

- Session transcript or state update.
- Draft/refined `_system/telos.md` after enough evidence.
- Stable split files: `_system/telos/mission.md`, `quarter-goals.md`, `values.md`, `dont-do.md`.
- Suggested TELOS-derived monitor feeds or research priorities when mature enough.

## Cost/Trust Constraints

- Use Tier A sparingly for synthesis; question selection can be cheaper.
- Respect daily USD 20 cap and TELOS weekly time cap.
- TELOS edits are medium risk because they steer future decisions; ask for approval before replacing stable sections.
- Do not infer identity from private content unless policy permits private model use.

## Relevant Helper Modules

- `skills/telos.interview/sessions.py`: session state, resume logic, draft assembly.
- Cost ledger/trust gate helper from task 06.

## Failure Handling

- If the user gives incomplete answers, save session state and resume later.
- If TELOS confidence is low, keep a draft section marked "provisional" instead of stabilizing it.
- If write approval is denied, return proposed text in Telegram and leave files unchanged.
