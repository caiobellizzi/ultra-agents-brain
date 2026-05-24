# Deferred Items from Plan 12-04

These items surfaced during the Task 6 `make test` gate after the Phase 12 eval-row changes were complete. They are outside Plan 12-04's file scope and were not changed by this plan.

## Out-of-Scope Test Failures

| Test | Observed failure | Reason deferred |
|------|------------------|-----------------|
| `tests/integration/test_memory_surface.py::test_mem_01_chat_run_persists_memory_within_5s` | Memory row appeared after ~17s; test budget is 5s. | Memory SLA / live AgentOS behavior, not eval row semantics. |
| `tests/test_agentos.py::TestAgentsImportable::test_curator_agent_has_memory_and_output_schema` | Curator has `update_memory_on_run=False`; test expected true. | Phase 11 explicitly opted curator/ingest out of automatic memory extraction. |
| `tests/test_agentos.py::TestAgentsImportable::test_research_agent_make_has_orchestrator_model_and_schema` | Research agent model is `research-worker`; test expected `orchestrator`. | Model routing expectation is unrelated to eval row correction. |
| `tests/test_telegram_adapter.py::TestRoutingLogic::test_plain_text_routes_to_supervisor` | Plain text routes to `chat`; test expected `supervisor`. | Telegram routing behavior is outside eval row correction. |
| `tests/test_telegram_adapter.py::TestRoutingLogic::test_unknown_command_falls_back_to_supervisor` | Unknown command routes to `chat`; test expected `supervisor`. | Telegram routing behavior is outside eval row correction. |

## Verification Notes

The Phase 12 Plan 12-04 focused checks passed:

- `PYTHONPATH=. .venv/bin/pytest tests/unit/test_eval_recorder.py tests/unit/test_eval_suite_hook.py tests/unit/test_eval_live_policy.py tests/unit/test_live_judge.py -q`
- `PYTHONPATH=. .venv/bin/pytest evals/ -q -m "not live"`
- `make eval-smoke`

`make test` was run both inside the sandbox and with elevated network permissions. The sandbox run also produced network-related local HTTP/Hugging Face failures; the elevated rerun reduced the result to the five out-of-scope failures above.
