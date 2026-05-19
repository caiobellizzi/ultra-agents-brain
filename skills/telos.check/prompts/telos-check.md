# TELOS Check Prompt

Evaluate a proposed action against TELOS.

Inputs:
- Proposed action, target paths, cost, reversibility, and user request.
- TELOS mission, quarter goals, values, and dont-do constraints.

Output YAML:
```yaml
alignment_score: 0.0
recommendation: approve | revise | defer | refuse
supports:
  - ""
concerns:
  - ""
approval_prompt: ""
missing_context:
  - ""
```

Rules:
- Medium-risk actions still require user approval.
- Refuse only when policy or explicit dont-do constraints are clear.
- Keep reasoning short enough for Telegram.
