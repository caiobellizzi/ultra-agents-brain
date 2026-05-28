# Eval Fixes and Live Judge Plan

## Context

Agno currently shows live agent runs as `Untitled Evaluation` rows with `eval_type=agent_as_judge` and `score=N/A`.

That happens because the current recorder writes live run telemetry into `agno_eval_runs` without setting `name`, without setting `evaluated_component_name`, and with `eval_data["score"] = None`. These rows are useful observability data, but they are not judged evaluations.

## Goals

- Make live run rows honest and readable in Agno.
- Keep scored eval rows separate from live telemetry rows.
- Add deterministic suite eval identities so repeated runs do not flood the dashboard.
- Add async live judging for selected live runs without blocking users.
- Keep a clean path to Agno-native `AgentAsJudgeEval` attachment later.

## Non-Goals

- Do not mutate or delete existing historical `Untitled Evaluation` rows.
- Do not enable live judging by default.
- Do not add a production systemd timer in the first pass.
- Do not block live user responses on judge model calls.

## Row Semantics

### Live Performance Rows

Live, unjudged agent runs should be written as performance rows.

- `eval_type`: `performance`
- `name`: `live:<agent_id>`
- `evaluated_component_name`: `<agent_id>`
- `agent_id`: `<agent_id>`
- `score`: `None`
- `eval_data.output`: captured agent output
- `eval_data.status`: `ok` or `error`
- `eval_data.latency_ms`: live run latency
- `eval_data.model_id`: live agent model id
- `eval_data.model_provider`: live agent model provider

These rows mean "what happened during a live run", not "how good it was".

### Suite Accuracy Rows

Pytest eval suite rows should remain scored accuracy rows.

- `eval_type`: `accuracy`
- `name`: `eval-suite:<agent_id>:<case_id>`
- `evaluated_component_name`: `<agent_id>`
- `agent_id`: `<agent_id>`
- `eval_data.score`: normalized `0.0` to `1.0`
- `eval_data.case_id`: dataset case id
- `eval_data.output`: test output or assertion summary

Suite rows should use deterministic run ids:

```text
suite:<agent_id>:<case_id>:<git_identity>
```

`git_identity` should be based on `HEAD` plus a dirty hash when eval-relevant files are modified.

Dirty hashing should include staged, unstaged, and untracked non-ignored files under eval-relevant paths:

- `agentos/`
- `evals/`
- `tests/`
- `ultra_brain/`
- `skills/`

Repeated runs for the same `{agent_id, case_id, git_identity}` should be treated as duplicates and skipped.

For rows where a real LLM judge determines the score, include the judge tier/model in identity. For deterministic field assertion rows, keep judge tier/model as metadata only.

### Live Judged Rows

Live judged rows should be separate child rows.

- `eval_type`: `agent_as_judge`
- `name`: `eval-live:<agent_id>:<rubric_id>`
- `evaluated_component_name`: `<agent_id>`
- `agent_id`: `<agent_id>`
- `eval_data.parent_run_id`: live performance row `run_id`
- `eval_data.rubric_id`: rubric id
- `eval_data.score`: normalized `0.0` to `1.0`
- `eval_data.raw_score`: raw judge score when available
- `eval_data.passed`: boolean pass/fail when available
- `eval_data.reason`: short judge rationale
- `eval_data.judge_model_id`: judge model id
- `eval_data.judge_model_provider`: judge model provider

Judged live rows should use deterministic run ids:

```text
judge:<parent_run_id>:<rubric_id>:<judge_model_id>
```

The original live performance row should remain as the source-of-truth run record.

## Live Judging Architecture

Use the worker design now, while keeping Agno-native eval attachment as a later path.

```text
live agent run
  -> write performance row
  -> decide eligibility and sampling at record time
  -> mark judge_status=pending when selected
  -> agentos live-judge worker reads pending rows
  -> worker runs judge/rubric
  -> worker writes child agent_as_judge row
  -> worker updates parent judge_status
```

### Why Worker Now, Agno Native Later

The repo already constructs `AgentAsJudgeEval` objects in `chat.py` and `query.py`, but current comments note that the installed Agno `Agent` does not accept an `evals=` kwarg yet. Direct Agno attachment is therefore not the right first implementation path.

The worker path is preferred now because it:

- avoids adding latency to user-facing responses
- supports sampling and retries
- can enforce privacy gates before judge calls
- survives process restarts because pending work is persisted in Postgres
- lets this repo control deterministic ids, names, parent linkage, and normalized scores

When Agno exposes a clean eval attachment API, rubrics can be attached natively using the same shared definitions.

## Live Judge Policy

Live judging is disabled by default.

Suggested env vars:

```bash
EVAL_LIVE_JUDGING_ENABLED=false
EVAL_LIVE_SAMPLE_RATE=0.0
EVAL_LIVE_SAMPLE_RATE_CHAT=
EVAL_LIVE_SAMPLE_RATE_QUERY=
EVAL_LIVE_SAMPLE_RATE_INGEST=
EVAL_LIVE_ALLOW_CONTENT_READ=false
EVAL_LIVE_MAX_ATTEMPTS=3
```

Use a global default sample rate plus per-agent overrides.

Eligibility and sampling should be decided at recording time. The worker should only process rows marked `judge_status="pending"`.

Parent live rows should include judge metadata such as:

```json
{
  "judge_eligible": true,
  "judge_sampled": true,
  "judge_status": "pending",
  "judge_reason": "sampled",
  "judge_rubric_ids": ["chat-citation"]
}
```

Status lifecycle:

- `not_eligible`
- `skipped`
- `pending`
- `judged`
- `error`

For errors, track:

- `judge_attempts`
- `last_error_type`
- `last_error_msg`
- `last_attempt_at`

Retry transient errors up to `EVAL_LIVE_MAX_ATTEMPTS`.

## Privacy Gate

Do not judge all sampled rows blindly.

The recorder or worker should skip rows with obvious sensitive markers, including:

- private key blocks
- API key or token-looking values
- password markers
- oversized payloads beyond configured limits

Full ingest content-quality judging must require:

```bash
EVAL_LIVE_ALLOW_CONTENT_READ=true
```

When this flag is false, ingest rows should either be skipped for full content quality or judged with metadata-only scope.

## Initial Live Judged Agents

Start with:

- `chat`
- `query`
- `ingest`

Do not add `research`, `curator`, or `supervisor` live judging in the first pass.

## Rubric Definitions

Create shared rubric definitions in:

```text
agentos/eval_rubrics.py
```

Each rubric should define:

- `rubric_id`
- `agent_id`
- `criteria`
- `scoring_strategy`
- `threshold`
- whether content reads are required
- whether the rubric can run metadata-only

Current `AgentAsJudgeEval` setup in agent factories should be built from the shared definitions rather than duplicating rubric text.

### Chat Rubric

`chat` should cite the vault when the user asks about vault contents, personal stored knowledge, notes, articles, or prior captured ideas. It should pass without citations for normal conversation or general non-vault questions.

### Query Rubric

`query` has an important distinction:

- The agent instructions currently forbid visible citation tokens/file paths in the final prose.
- The schema has a structured `citations` field.

The judge should evaluate groundedness in retrieved vault evidence and structured citations, not require visible markdown citation tokens in the final user-facing text.

### Ingest Rubric

`ingest` should use a combined content-quality rubric:

- source faithfulness
- no invented claims
- useful title/path/tags/frontmatter
- appropriate `needs_review`

If original source content is unavailable, run a metadata-only partial rubric and mark:

```json
{
  "judge_scope": "metadata_only"
}
```

Do not score unavailable source content as `0.0` solely because the source could not be fetched.

## Worker CLI

Add a subcommand under `agentos`:

```bash
python -m agentos live-judge --once
```

Preserve existing behavior:

```bash
python -m agentos
```

should still start the AgentOS server.

The worker should support:

```bash
python -m agentos live-judge --once --limit 10
python -m agentos live-judge --loop --interval 60 --limit 10
```

Defaults:

- default mode: `--once`
- default limit: `10`
- loop mode only when explicitly requested

## Worker DB Behavior

Use Agno DB API for discovery first:

```python
db.get_eval_runs(eval_type=[EvalType.PERFORMANCE], ...)
```

Filter rows where `eval_data.judge_status == "pending"`.

Use direct SQL in one isolated helper to update parent `eval_data`, because Agno exposes `rename_eval_run()` but no general update helper. This helper may use the same private-ish primitives Agno uses internally:

- `db._get_table(table_type="evals")`
- `db.Session()`

Keep this contained so it is easy to replace if Agno adds an official update API.

## Score Normalization

Use normalized dashboard scores:

- binary pass: `1.0`
- binary fail: `0.0`
- numeric `1-10`: `raw_score / 10`

Store raw details separately:

- `raw_score`
- `passed`
- `reason`
- rubric-specific breakdown fields

## Implementation Steps

1. Update `agentos/eval_recorder.py`.
   - Live rows use `EvalType.PERFORMANCE`.
   - Set `name=live:<agent_id>`.
   - Set `evaluated_component_name=<agent_id>`.
   - Keep `eval_data["score"] = None`.
   - Add eligibility/sampling metadata when live judging is enabled.

2. Add deterministic suite identity helpers.
   - Compute git identity from `HEAD` plus dirty hash over eval-relevant paths.
   - Update `evals/conftest.py` to use deterministic run ids.
   - Set suite row `name` and `evaluated_component_name`.
   - Keep duplicate handling as skip-on-existing/integrity error.

3. Add `agentos/eval_rubrics.py`.
   - Define shared rubrics for `chat`, `query`, and `ingest`.
   - Refactor existing unused `AgentAsJudgeEval` setup to build from these definitions.

4. Add live judge policy helpers.
   - Env parsing.
   - Sample rate resolution.
   - Eligibility checks.
   - Privacy gate checks.

5. Add live judge worker.
   - Discover pending performance rows.
   - Select rubrics by agent.
   - Build judge input from row input/output and optional source/note content.
   - Use Agno judge logic for evaluation.
   - Write controlled `EvalRunRecord` child rows.
   - Update parent status metadata.

6. Add `agentos` CLI subcommand.
   - Preserve default server startup.
   - Add `live-judge --once`.
   - Add explicit `--loop --interval`.
   - Add `--limit`.

7. Add offline tests.
   - Recorder naming/type metadata.
   - Deterministic suite ids.
   - Dirty git identity behavior with fake inputs where practical.
   - Rubric selection.
   - Privacy gate.
   - Worker status transitions.
   - Score normalization.

8. Update docs.
   - `docs/MAINTENANCE.md` should describe row meanings, env flags, and worker commands.

## Verification

Required offline verification:

```bash
.venv/bin/pytest <focused tests> -q
make test
make eval-smoke
```

Live Postgres/model evals are optional and should remain opt-in because they depend on deployed services and may cost money.

## Future Follow-Ups

- Attach shared rubrics directly to Agno agents when the installed Agno API supports it cleanly.
- Add production systemd timer for `python -m agentos live-judge --once`.
- Add cleanup tooling for historical `Untitled Evaluation` rows only if they remain operationally noisy.
- Add live judging for `research`, `curator`, and `supervisor` after defining stronger rubrics.
