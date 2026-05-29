# Phase 11 RESEARCH — Memory Surface Activation

> Inline research (produced by main agent, not by a gsd-phase-researcher sonnet subagent — hit a Sonnet limit at the time of writing; reverted to main-context Opus 4.7 research). All Agno citations are against the **locally-installed Agno 2.6.7** under `.venv/lib/python3.13/site-packages/agno/` — which is the authoritative reference for the version actually running in prod.
> Context7 was attempted per operator request and returned a transport-level `Bad Request: No valid session ID provided` on every call; falling back to the local venv is the safer choice anyway since Context7 would return docs for "current" upstream, not 2.6.7.

## 0. Phase 11 ground truth (the operator's screenshot was directionally right but incomplete)

The operator's reframing (paraphrased from the screenshot): *"Agno has 2 memory paths — automatic LLM extraction via `enable_user_memories=True` + `MemoryManager`, or explicit `db.upsert_user_memory()`. Neither is wired in our stack: agents don't pass `enable_user_memories=True` / `memory_manager=…`, no code calls `upsert_user_memory`, result agno_memories stays at 0 rows."*

The reframing is **directionally correct** (we need auto-extraction) but **incomplete** in two ways that the next-step plan must absorb:

1. **The flag was renamed.** In Agno 2.6.7, `enable_user_memories` is being deprecated. `agent.py:402-403` reads:
   ```python
   update_memory_on_run: bool = False,
   enable_user_memories: Optional[bool] = None,  # Soon to be deprecated. Use update_memory_on_run
   ```
   And `agent.py:534-538`:
   ```python
   if enable_user_memories is not None:
       self.update_memory_on_run = enable_user_memories
   else:
       self.update_memory_on_run = update_memory_on_run
   self.enable_user_memories = self.update_memory_on_run  # Soon to be deprecated. Use update_memory_on_run
   ```
   The two flags are **aliases**. Setting either one sets the other.
2. **Our agents DO pass `memory_manager=`.** `grep -n memory_manager= agentos/agents/` returns 6 lines (one per factory call site at `chat.py:42`, `query.py:42`, `research.py:30`, `curator.py:24`, `ingest.py:28`, `supervisor.py` line ~30). The `MemoryManager` singleton is constructed at `agentos/app.py:45-49` and passed verbatim to every factory.
3. **Our agents DO set the modern flag.** `grep -n update_memory_on_run= agentos/agents/` returns 6 lines (`chat.py:44`, `query.py:44`, `research.py:32`, `ingest.py:30`, `supervisor.py:50`, `curator.py:26`). Since `update_memory_on_run` is aliased to `enable_user_memories`, **the gates are already set**.

So why is `agno_memories` still at 1 row? Because the gates being set is necessary but not sufficient. The real question this phase has to answer is: *what's between "the gates are set" and "a row appears within 5 seconds of a real chat run"?*

## 1. The actual extraction path — line-by-line trace (Agno 2.6.7)

The function that decides whether to extract memory at the end of a run is `make_memories()` at `agno/agent/_managers.py:29-82`. Reproduced verbatim (with line numbers):

```
# _managers.py:38-51 (gate + invocation)
if (
    user_message_str is not None
    and user_message_str.strip() != ""
    and agent.memory_manager is not None
    and agent.update_memory_on_run
):
    log_debug("Managing user memories")
    agent.memory_manager.create_user_memories(
        message=user_message_str,
        user_id=user_id,
        agent_id=agent.id,
        run_metrics=collector,
    )
```

Three required conditions:

| Condition | Our status (2026-05-22) |
|---|---|
| `user_message_str is not None and != ""` | ✅ Every Telegram → AgentOS round-trip sends a non-empty message (verified at `channels/telegram_adapter.py:309` — `data["message"] = body`). |
| `agent.memory_manager is not None` | ✅ All 6 factories pass `memory_manager=memory_manager` and the singleton is constructed at `agentos/app.py:45-49`. |
| `agent.update_memory_on_run` | ✅ All 6 factories set `update_memory_on_run=True` (alias of `enable_user_memories`). |

So `create_user_memories(...)` **is being called** on every run. The question shifts from "is the gate open?" to "what happens inside `create_user_memories()`?"

`MemoryManager.create_user_memories()` lives at `agno/memory/manager.py:368-419`. Key behavior:

- If `user_id is None`, it **defaults to `"default"`** (line 397-398: `if user_id is None: user_id = "default"`). So even without telegram plumbing, rows would still get written under `user_id="default"`.
- It calls `self.create_or_update_memories(...)` (line 406-416). That method makes an **LLM call** to extract durable facts from the conversation.
- The LLM call uses the model attached to the `MemoryManager` — in our case `chat_model("cheap-worker")` (see `agentos/app.py:47`).

## 2. Why the 1 row exists + what it tells us

The single row in `ai.agno_memories`:

```json
{
  "memory_id": "923150df-…",
  "memory": "User completed an 'aider' task involving adding a hello world function to utils.py using cloud-sonnet+private-worker model, …",
  "topics": ["work", "coding", "task"],
  "agent_id": null,
  "team_id": null,
  "user_id": "workshop",
  "updated_at": "2026-05-22T19:00:51Z"
}
```

Two important corrections to the audit's earlier reasoning:

- **`agent_id=null` does NOT prove it was a manual UI entry.** Our agents construct with `Agent(name="chat", …)` but **without** passing `id=...`. `agent.py:505` does `self.id = id`, so `agent.id is None` for all our agents. That means **any** agent-run-generated row has `agent_id=null` today. The audit's earlier inference ("agent_id=null → manual UI entry") was wrong.
- **`user_id="workshop"` is the smoking gun.** Telegram numeric IDs look like `8523719`, not `"workshop"`. So this row was almost certainly created by a **manual seed** — either a curl probe (`curl -d user_id=workshop -d message=…`), a workshop demo session that hard-coded `user_id="workshop"`, or a UI "+ CREATE MEMORY" entry. It was **not** produced by a real Telegram user → chat agent round-trip.

What this tells us: the extraction LLM probably **did** fire for that one workshop session, and the path **does** work end-to-end. The reason no Telegram-driven rows exist is one of:

- *(hypothesis A — most likely)* Real production Telegram traffic since deployment has been thin or non-memory-worthy. The audit's pg_stat data supports this: `agno_sessions` has 39 inserts in the deployment window, mostly likely workshop / demo / smoke traffic.
- *(hypothesis B — second-most-likely)* The extraction LLM call is **failing silently** for production runs. The MemoryManager uses `chat_model("cheap-worker")`, which routes through LiteLLM. The phase 10 audit noted a known LiteLLM issue (memory ID S21770) where `response_format` + tools is incompatible on some providers. If the extraction call uses a structured response_format and the worker model can't satisfy it, the call would 400 from LiteLLM and the row would be silently dropped (the LLM call result feeds `create_or_update_memories`, which can swallow errors). **This needs to be empirically verified.**
- *(hypothesis C — least likely)* `Agent.id is None` somehow disables extraction. Reading `_managers.py:38-51` carefully shows it doesn't — `agent.id` is just passed through to `create_user_memories(agent_id=agent.id, …)` and ends up as a column value, not a gate.

The phase 11 plan must include a step that empirically distinguishes A from B (and rules out C). The cleanest test: send one real Telegram message containing memory-worthy content with a real Telegram user_id, then within 5 seconds query `/memories?user_id=<that-id>`. If a row appears: hypothesis A; the system was just thin on traffic. If no row appears and the AgentOS log shows the extraction call: hypothesis B, the LLM extraction is silently failing — phase 11 fixes the LiteLLM mapping / model choice.

## 3. What's already in place — inventory

The phase 11 plan should NOT redo any of these:

| Piece | Where | Evidence |
|---|---|---|
| Shared `PostgresDb` adapter | `agentos/app.py:25-43` (`db = PostgresDb(db_url=os.environ["POSTGRES_DSN_SESSIONS"], …)`) | Audit `evidence/wiring.md` §4 |
| `MemoryManager` singleton | `agentos/app.py:45-49` (one instance, all factories share it) | Audit `write-gate-grep.txt` |
| `memory_manager=` plumbed into every factory call | `agentos/agents/{chat,curator,ingest,query,research,supervisor}.py` lines 42, 24, 28, 42, 30, ~30 | grep |
| `update_memory_on_run=True` on every factory | Same files, lines 44, 26, 30, 44, 32, 50 | grep |
| `enable_agentic_memory=True` on every factory | Same files, lines 43, 25, 29, 43, 31, 49 | grep |
| `MemoryManager` invocation site | `agno/agent/_managers.py:38-51` (make_memories) | source read |
| `MemoryManager.create_user_memories` extraction logic | `agno/memory/manager.py:368-419` | source read |
| `db.upsert_user_memory` write | `agno/db/postgres/postgres.py:1653` (sync) / `async_postgres.py:1532` (async) | audit citation |
| Telegram `user_id` plumbing → AgentOS POST | `channels/telegram_adapter.py:309` (`data["user_id"] = str(user_id)`) | grep |
| `ai.agno_memories` table schema | `evidence/psql.txt` (audit) | psql output |
| AgentOS deployment as systemd service | `evidence/wiring.md` §1 | audit |

## 4. What's missing — concrete delta for phase 11

The plan needs to deliver these in order:

### 4a. Precondition (1 line) — DIAG-BL-01

Pin the shared `BaseDb.id`. In `agentos/app.py:25-43`, change:

```python
db = PostgresDb(db_url=os.environ["POSTGRES_DSN_SESSIONS"], …)
```

to

```python
db = PostgresDb(id="ultra-brain-main", db_url=os.environ["POSTGRES_DSN_SESSIONS"], …)
```

Per `agno/db/base.py:56` (`self.id = id or str(uuid4())`), this makes the registered `db_id` deterministic across redeploys instead of regenerating a fresh UUID per process. Resolves DIAG-BL-01 and satisfies MEM-02.

### 4b. Set a stable `agent.id` on every Agent factory — silent gap

Today, every `Agent(name="chat", …)` constructs without an explicit `id`, so `agent.id is None` (verified `agent.py:505`). The memory row ends up with `agent_id=null`, which:

- Breaks the OBS-01 contract ("agent_id" must appear in the structured log line).
- Makes per-agent memory analytics impossible.
- Creates a downstream surprise for whoever queries `agno_memories.agent_id`.

**Add `id="chat"`, `id="curator"`, etc. to every `Agent(...)` constructor.** Mirror the existing `name=` value. This is a 6-line change across the agent files and has zero behavioral risk.

### 4c. Diagnose hypothesis A vs B empirically — required investigation step

Per §2 above, before changing extraction behavior, the plan must run **one controlled experiment**:

1. Send a real Telegram message ("My favorite color is teal and I bike to work every Tuesday") to the bot with a real user_id.
2. Wait 5 seconds. Query `/memories?user_id=<telegram-id>`.
3. If row appears → hypothesis A confirmed. Phase 11 work is "make sure traffic happens" + observability.
4. If no row appears → hypothesis B confirmed. Inspect `uab-brain.service` journal logs for the extraction LLM call. Likely fix: switch the `MemoryManager` model from `cheap-worker` to a worker that returns structured JSON cleanly (or strip `response_format` for the extraction call via the existing LiteLLM `strip_response_format` hook — see memory S21777, S21780).

This is **not optional**. Without empirical proof, the rest of phase 11 is guesswork.

### 4d. Add `enable_user_memories=True` redundantly — defense-in-depth (optional)

Even though `update_memory_on_run=True` is the modern flag and is aliased to `enable_user_memories`, some test fixtures or migrations may still inspect `enable_user_memories` directly (e.g. the dashboard schema at `agno/os/routers/agents/schema.py:210`). Adding `enable_user_memories=True` explicitly is a no-op behaviorally but makes the codebase greppable for the operator's expectation. **Recommendation: don't add it.** The deprecation will land, and adding deprecated flags is technical debt. Just document in code that `update_memory_on_run=True` is the active flag and that `enable_user_memories` is its alias.

### 4e. OBS-01 instrumentation — structured log line per memory write

The OBS-01 contract: each memory write emits a log line with `{level, path=memory, agent_id, db_id, row_id, latency_ms, status}` on success and failure.

Three viable hook points (the plan must pick one):

1. **Wrap `MemoryManager.create_user_memories`** — subclass `MemoryManager` to a project-local `InstrumentedMemoryManager` that wraps the method with timing + logging. Pros: doesn't depend on Agno internals; survives Agno upgrades. Cons: not all writes go through this method (explicit upserts via `db.upsert_user_memory()` won't be caught).
2. **Wrap `db.upsert_user_memory`** — subclass `PostgresDb` and override `upsert_user_memory`. Pros: catches every memory write regardless of caller. Cons: tightly coupled to the Agno DB API surface; breaks on Agno upgrade if the method signature changes.
3. **Use an Agno run hook** — `agno/agent/_hooks.py` exposes lifecycle hooks. Look at the structure and see if there's a `post_run` or `after_memory_update` hook we can register without subclassing.

**Recommendation: option 1** (wrap MemoryManager). It's the highest-leverage / lowest-risk choice — the explicit-upsert path is operator-controlled (curl/UI), where logs already exist anyway. Phase 11 should also add a smoke test that the log line is emitted (assert the log capture sees the path=memory record on a real run).

### 4f. Choose which agents get auto-extraction — opt-out for the wrong ones

The screenshot suggested *"most likely the Telegram-facing brief/chat agents"*. Reviewing the 6 factories:

| Agent | Should auto-extract? | Why |
|---|---|---|
| **chat** | **Yes** | Conversational, user-stable identity from Telegram. Primary memory source. |
| **research** | **Yes** | Conversational, user-id stable. Memory worth keeping. |
| **query** | **Yes** | Conversational, user-id stable. Memory worth keeping. |
| **supervisor** (team) | **Probably yes** | If a team conversation produces memory-worthy facts, attribute via `team_id`. The make_memories path already supports this. |
| **curator** | **No** | Background processing, not user-facing. Set `update_memory_on_run=False`. Eliminates LLM cost surprise. |
| **ingest** | **No** | One-shot bulk operations. Set `update_memory_on_run=False`. |

The current code sets `update_memory_on_run=True` on all 6. The plan should change curator and ingest to `False`.

## 5. Decision points the planner needs operator answers for

| # | Question | Default recommendation |
|---|---|---|
| 1 | Should curator + ingest get `update_memory_on_run=False`? | **Yes, set to False.** |
| 2 | OBS-01 hook location — wrap MemoryManager, wrap PostgresDb, or use Agno hooks? | **Wrap MemoryManager (option 1 above).** |
| 3 | Hypothesis A vs B — should the plan include the controlled-experiment step before writing code? | **Yes — it's a 10-minute step that decouples phase 11 from speculation.** |
| 4 | If hypothesis B is confirmed, fix by upgrading the MemoryManager model or by extending the LiteLLM `strip_response_format` hook? | **Defer until empirical evidence; document both options in the SUMMARY.** |
| 5 | Should `agent.id` be set explicitly on every factory? | **Yes — 6-line change, fixes a silent gap in OBS-01.** |
| 6 | Should the explicit-upsert path (`/memories` POST) also be instrumented? | **Optional. The OBS-01 contract is "per memory write"; the wrap-MemoryManager hook covers the auto path only. Defer to a later observability phase.** |
| 7 | What `user_id` shape do we want? Telegram numeric IDs are stable but anonymous. Should we map Telegram → human-readable in a translation layer? | **Defer — out of phase 11 scope. Use raw Telegram numeric ID for now; document the choice.** |

## 6. Test strategy — MEM-01, MEM-02, MEM-03 verification

### MEM-01 (5-second SLA)

Integration test (under `tests/integration/test_memory_surface.py`):

1. Construct the chat agent with the real wiring (or use the deployed VPS).
2. Send a memory-worthy message to `POST /agents/chat/runs` with `user_id="test-mem-01"`.
3. Wait up to 5 seconds. Poll `GET /memories?user_id=test-mem-01`.
4. Assert `data` is non-empty within the 5 s window.

**Caveat:** this test requires a working extraction LLM (LiteLLM + a worker model). Mark it as `@pytest.mark.live` and skip it in unit-CI runs. Add a separate **smoke check** (`make check-memory` or a one-liner script) that runs it against the prod deployment after each deploy.

### MEM-02 (db_id scoping)

Unit assertion:

1. Import `agentos.app`.
2. Inspect `app.db.id`.
3. Assert it equals `"ultra-brain-main"`.

Also assert `GET /config` returns `databases[0] == "ultra-brain-main"`. Plus a manual psql check: `SELECT user_id FROM ai.agno_memories WHERE updated_at >= now() - interval '5 minutes'` after a smoke run.

### MEM-03 (`update_memory_on_run=True` verified)

Unit assertion in `tests/unit/test_agent_factories.py`:

```python
def test_chat_agent_has_memory_extraction():
    agent = make_chat_agent(memory_manager=Mock(), knowledge=Mock(), db=Mock())
    assert agent.update_memory_on_run is True
    assert agent.enable_user_memories is True  # alias proof
    assert agent.memory_manager is not None

def test_curator_agent_has_no_memory_extraction():
    agent = make_curator_agent(memory_manager=Mock(), db=Mock())
    assert agent.update_memory_on_run is False
```

(Curator test only passes after delta 4f is applied.)

### OBS-01 verification

Unit test that captures `logging` output during a mocked `create_user_memories` call and asserts the structured fields are present (`path=memory`, `agent_id`, `db_id`, `row_id`, `latency_ms`).

## 7. Threat model & risks

| Risk | Mitigation |
|---|---|
| **Memory-extraction LLM cost** — every chat run triggers an LLM extraction call. Could 2x the LLM cost per conversation. | Use `cheap-worker` model (already configured). Add a per-day cost budget alert. Phase 15 may want a cost ceiling. |
| **PII / sensitive content** — auto-extracted memories may capture passwords, secrets, etc. that the user mentioned in chat. | Add a memory-content redaction filter in the wrap-MemoryManager layer (regex for common secret shapes). Defer the full PII strategy to phase 15. |
| **LLM extraction failure cascade** — if the extraction LLM 500s or times out, does it block the parent agent run? | Read `_managers.py:38-51` carefully — the call is synchronous (`make_memories()` is a sync function called from the run pipeline). A failure would propagate. Verify experimentally and consider wrapping the call in try/except. |
| **LiteLLM `response_format` + tools incompatibility** — already known (S21770, S21777). If the extraction LLM happens to also have tools attached, the call 400s. | The `strip_response_format` hook (deployed per S21777-S21780) should handle this. Verify it covers the extraction code path during hypothesis-B investigation. |
| **`user_id="default"` accumulation** — if any call site forgets to pass `user_id`, all those rows accumulate under `user_id="default"` and become an analytics-poisoning bucket. | Add a startup assertion or lint rule that every `agent.run()` call site must pass `user_id`. Or: change `MemoryManager.create_user_memories` to skip writes when `user_id is None` (would require subclassing). Recommend the lint approach. |
| **Telegram-only coverage** — HTTP API + A2A + MCP entry points may not plumb `user_id`. | Phase 11 plan should grep for every entry point and confirm `user_id` plumbing. Out-of-Telegram paths may need a `user_id="anonymous"` default until those channels are designed. |
| **AgentOS open auth (DIAG-BL-09)** — anyone on the internet can POST to `/agents/chat/runs` and seed arbitrary memories. | Out of phase 11 scope. Track as DIAG-BL-09 → phase 15 security work. Note in plan as a known exposure. |

## 8. References

| # | File | Lines | What it proves |
|---|---|---|---|
| 1 | `agno/agent/agent.py` | 122-124, 402-403, 534-538 | `enable_user_memories` is being deprecated; aliased to `update_memory_on_run`. Setting either sets the other. |
| 2 | `agno/agent/_managers.py` | 29-82 (sync), 83-135 (async) | `make_memories()` gating predicate and invocation site. The path our agents already satisfy. |
| 3 | `agno/memory/manager.py` | 368-419 | `MemoryManager.create_user_memories()` — defaults `user_id=None` → `"default"`; calls extraction LLM via `create_or_update_memories()`. |
| 4 | `agno/memory/manager.py` | 566, 857, 928, 930 | Concrete `self.db.upsert_user_memory(memory=…)` write calls that produce the row. |
| 5 | `agno/db/postgres/postgres.py` | 1653 (sync), 1912 (async) | The actual DB write — same citation as audit. |
| 6 | `agno/db/base.py` | 56 | `self.id = id or str(uuid4())` — basis for the DIAG-BL-01 `id="ultra-brain-main"` pin. |
| 7 | `agno/agent/agent.py` | 505 | `self.id = id` — proves our `agent.id is None` because factories don't pass it. Justifies delta 4b. |
| 8 | `agentos/app.py` | 25-49, 58-74 | Current shared `db` + `MemoryManager` wiring. The 1-line `id=` pin + factory id= adds are the only required edits to this file. |
| 9 | `agentos/agents/chat.py` | 38-79 | Current chat factory — passes `memory_manager`, `enable_agentic_memory=True`, `update_memory_on_run=True`. Confirms the gates are set. |
| 10 | `agentos/agents/{curator,ingest}.py` | 24-30 | Current curator/ingest factories — also set `update_memory_on_run=True`. Phase 11 should flip these to False (delta 4f). |
| 11 | `channels/telegram_adapter.py` | 285-310 | `route_message()` plumbs `user_id=str(user_id)` via HTTP form data to `POST /agents/{id}/runs`. Confirms Telegram path passes user_id. |
| 12 | `.planning/phases/10-diagnostic-audit/evidence/memories.json` | full | The 1 row in `ai.agno_memories` — `user_id="workshop"` not numeric; almost certainly a workshop seed, not a real Telegram-driven row. |
| 13 | `.planning/phases/10-diagnostic-audit/evidence/wiring.md` | §1, §4 | AgentOS as systemd not docker; PostgresDb backend confirmed. |
| 14 | `.planning/phases/10-diagnostic-audit/AUDIT.md` | memory section (amended) | Corrected RC tag `RC-memory-wrong-path-wired`. |
| 15 | `.planning/phases/10-diagnostic-audit/DB-ID-DECISION.md` | Phase 11 consequences (amended) | Option A `id="ultra-brain-main"` is the precondition. |
| 16 | `.planning/phases/10-diagnostic-audit/BACKLOG.md` | DIAG-BL-04 (amended), DIAG-BL-01 | Phase 11 precondition lineage. |
