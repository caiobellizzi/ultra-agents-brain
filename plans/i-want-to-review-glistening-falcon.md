# Make the Eval Surface Trustworthy — Live Auto-Scoring

## Context

The AgentOS eval table (`agno_eval_runs`, DB `ultra-brain-main`) shows rows as **"Untitled Evaluation", SCORE = N/A, MODEL = N/A**, with outputs like *"I have tools to execute, but I need confirmation."* The eval surface is logging noise and never scoring anything — so the "signal layer" that any future self-improvement work depends on does not actually produce signal.

Root causes (traced against the live code + Agno 2.6.7):

1. **No score** — the live judge that computes scores (`agentos/live_judge.py` + `eval_rubrics.py` + `eval_live_policy.py`) is fully built but **switched off and never deployed**: `EVAL_LIVE_JUDGE_ENABLED` unset → `enabled=False`; `EVAL_LIVE_SAMPLE_RATE` unset → `0.0`; no systemd/cron worker runs `python -m agentos live-judge`. The recorder writes `eval_data["score"]=None`; only the judge ever fills it.
2. **"Untitled" + "Agent As Judge"** — these rows were created manually from the AgentOS UI ("NEW EVAL") with the Name field left blank → `name` stored NULL → frontend renders "Untitled".
3. **Paused-run noise + Model N/A** — `InstrumentedEvalRecorder` records the *paused* HITL invocation (incomplete run, no model). `_extract_model` also drops `response.model_provider` for string models.
4. **HITL completion never recorded** — the recorder patches only `run`/`arun`. HITL resume runs through `agent.acontinue_run()` (a different method). So HITL agents (`ingest`, `research`) get **one bad partial row + zero rows for the completion**.

**Decisions locked with the user (2026-05-29):**
1. Fix the eval surface first; re-plan self-evolution later as its own milestone.
2. **Live auto-scoring** is the trustworthy source of title+score (abandon the manual UI eval path).
3. Add rubrics for **curator + research**; defer the supervisor Team.
4. Run the judge via a **systemd timer, `--once` every ~2 min**.
5. **Back up, then delete** the existing junk rows.

Intended outcome: the eval table shows named, scored rows for real traffic across all 5 specialists, with no paused-run noise and no "Untitled" rows.

---

## Work Items

### A. Fix the recorder — `agentos/eval_recorder.py`

The recorder currently writes a row for every `run`/`arun`, including paused runs, and misses HITL completions. Four surgical changes:

- **A1 — Skip paused responses.** In the `patched_run`/`patched_arun` wrappers (alongside the existing `stream`/`background` skip), do not record when the response is paused:
  ```python
  if response is not None and getattr(response, "is_paused", False):
      return response  # incomplete; the resumed run is recorded via acontinue_run
  ```
  (`is_paused` is the same attribute the Agno router uses; `RunStatus.paused` lives in `agno/run/base.py`.)
- **A2 — Patch the resume path (critical).** Add `make_acontinue_run`/`make_continue_run` closures mirroring the existing `make_arun`/`make_run`, and patch them on **both** `Agent` and `Team` inside `patch_classes_for_recording`. Without this, `ingest`/`research` never get a scorable row. Reuse the same `_eval_recorder_patched` idempotency guard and the `_record` path. The completed resumed `RunOutput` carries the real `run_id`, model, and output.
- **A3 — Fix `_extract_model` provider.** In the `isinstance(model, str)` branch, return the provider instead of `None`:
  ```python
  if isinstance(model, str):
      return model, getattr(response, "model_provider", None)
  ```
- **A4 — Don't queue errored runs for judging.** When `error is not None`, record the row with `status="error"` (already done) but skip `_add_live_judge_metadata` so the judge never tries to score a failure.

### B. Add two rubrics — `agentos/eval_rubrics.py`

Append to `LIVE_RUBRICS`, matching the existing `EvalRubric` dataclass shape (mirror `query-groundedness-v1`):

- **`curator-quality-v1`** — `agent_id="curator"`, `scoring_strategy="numeric"`, `threshold=0.7`, `requires_content_read=False`, `metadata_only_supported=True`. Criteria: *"The curated note adds value, has correct tags, and links to existing notes when relevant."*
- **`research-grounding-v1`** — `agent_id="research"`, `scoring_strategy="numeric"`, `threshold=0.7`, `requires_content_read=True`, `metadata_only_supported=True`. Criteria: *"The report cites its sources, conclusions are traceable to the evidence, and nothing is fabricated."*

(Supervisor Team deferred — routing quality needs a bespoke rubric, and `Team` lacks several Agent features.)

### C. Enable + deploy the live judge

- **C1 — Env** (`/opt/ultra-agents-brain/.env` on the VPS; also document in the repo's `.env.example` if present):
  ```
  EVAL_LIVE_JUDGE_ENABLED=true
  EVAL_LIVE_SAMPLE_RATE=1.0
  ```
  Sample rate 1.0 is safe: traffic is low and the judge runs on the **free local** `private-worker` (Gemma via LM Studio). Dial down later if load warrants.
- **C2 — New systemd units** in `deploy/systemd/` (mirror `uab-digest.*` + `uab-brain.service`):
  - `uab-live-judge.service` — `Type=oneshot`, `User=uabrain`, `WorkingDirectory=/opt/ultra-agents-brain`, `EnvironmentFile=/opt/ultra-agents-brain/.env`, `ReadWritePaths=/srv/second-brain /var/log/ultra-agents-brain /var/lib/uab`, `ExecStart=/opt/ultra-agents-brain/.venv/bin/python -m agentos live-judge --once --limit 20`, `After=uab-brain.service`.
  - `uab-live-judge.timer` — `OnUnitActiveSec=2min` (+ `OnBootSec=2min`), `Persistent=true`, `WantedBy=timers.target`.
- **C3 — Install on VPS** (rsync-based deploy): rsync the repo, `cp deploy/systemd/uab-live-judge.* /etc/systemd/system/`, `systemctl daemon-reload`, `systemctl enable --now uab-live-judge.timer`. The brain service needs a restart to pick up the new `.env` flags so live traffic is marked judge-pending.

### D. Clean up the junk rows (production Postgres)

- **D1 — Backup:** `pg_dump` the `agno_eval_runs` table (schema `ai`) before any delete.
- **D2 — Inspect first:** `SELECT count(*) ... GROUP BY` on `name IS NULL` and on paused-message outputs to confirm scope.
- **D3 — Delete, keeping legitimate rows:** remove untitled UI evals and recorded paused rows; **keep** pytest-suite rows (`name LIKE 'eval-suite:%' OR name LIKE 'suite:%'`) and any real `live:`/`eval-live:` rows. Predicate (run as `SELECT` first, then `DELETE`):
  ```sql
  WHERE name IS NULL
     OR eval_data->>'output' ILIKE '%need confirmation%';
  ```

### E. Review of the existing Self-Evolving Agents plan (deferred — do not build now)

`plans/i-want-to-implement-woolly-kahan.md` stays on disk but must be corrected before it is built (captured in memory `self-evolving-agents-plan-corrections`):
1. Phase 1 "wire judges to post_hooks" is stale — replace with "enable + deploy the live judge" (this plan delivers the foundation).
2. Phase 2 cannot use `mcp__obsidian` in the runtime — use `Path.write_text` + `query_vault`.
3. Phase 3 culture is **Agent-only** in Agno 2.6.7 (not Team), and the prod DB is Postgres, not SQLite.

---

## Critical Files

| File | Change |
|---|---|
| `agentos/eval_recorder.py` | A1 skip paused · A2 patch `acontinue_run`/`continue_run` on Agent+Team · A3 provider fix · A4 no-judge-on-error |
| `agentos/eval_rubrics.py` | B add `curator-quality-v1`, `research-grounding-v1` |
| `/opt/ultra-agents-brain/.env` (VPS) + `.env.example` | C1 enable flags |
| `deploy/systemd/uab-live-judge.service` (NEW) | C2 oneshot worker |
| `deploy/systemd/uab-live-judge.timer` (NEW) | C2 every 2 min |
| Production Postgres `ai.agno_eval_runs` | D backup + delete junk |
| `README.md` | README-sync: new systemd units + env vars |

Reused as-is: `agentos/live_judge.py`, `agentos/eval_live_policy.py`, `agentos/__main__.py` (`live-judge` CLI), `agentos/app.py` (`patch_classes_for_recording` install), `agentos/model.py` (`private-worker` tier).

---

## Verification (end-to-end)

1. **Unit/regression:** `make eval-smoke` stays green. Add a recorder test asserting (a) a paused `RunOutput` produces **no** row, (b) a completed `acontinue_run` produces exactly one row, (c) `_extract_model` returns a non-null provider for a string model.
2. **Recorder + resume:** trigger an `ingest` run via Telegram, approve the HITL prompt; confirm exactly one PERFORMANCE row `name="live:ingest"` with a real model — and **no** paused-message row.
3. **Judge worker:** after enabling, run each agent (chat, query, ingest, curator, research) once; within ~2 min confirm child rows `name="eval-live:{agent}:{rubric}"` with a numeric/binary `score` in `eval_data`. `journalctl -u uab-live-judge` shows clean passes.
4. **UI check:** the AgentOS eval table shows titles + scores, no "Untitled", no "need confirmation" rows.
5. **Cleanup:** post-delete `SELECT count(*)` matches the inspected scope; pytest-suite rows still present.

---

## Risks & Mitigations

- **`acontinue_run` not surviving `agent.deep_copy()` per request** — the existing recorder patches at the **class** level precisely for this reason; the new `acontinue_run`/`continue_run` patches follow the same pattern, so they survive. Verify with a real Telegram HITL round-trip (step 2).
- **Judge load at sample rate 1.0** — judge is the free local Gemma; if LM Studio saturates, drop `EVAL_LIVE_SAMPLE_RATE` or add `EVAL_LIVE_SAMPLE_RATE_<AGENT>` overrides.
- **Destructive DELETE on prod** — always `pg_dump` first (D1) and run the predicate as `SELECT` before `DELETE` (D2/D3).
- **Sync vs async HITL paths** — patch both `acontinue_run` and `continue_run` (and the Team variants) so a sync resume isn't missed.
