# T7.3 Evaluation Runner

## Architecture

- `evaluation/runner.py` creates a fresh `SupportSession` per case, initializes declared State facts in place, executes all case turns through the existing `process_turn()`, and keeps a suite running after a case error.
- `evaluation/evaluators.py` compares expectations against `TurnTrace` in the fixed order extraction, state, workflow, retrieval, vision, tool, and answer.
- `evaluation/report.py` formats terminal output and JSON containing checks and Trace IDs without embedding complete Trace payloads.
- `evaluation/cli.py` selects one case, one category, or the complete dataset.

The Runner does not reproduce Workflow, RAG, Vision, Tool, Agent, or orchestration logic.

## Evaluation semantics

Each layer returns PASS, FAIL, or SKIP. SKIP means no expectation was defined. Case execution exceptions produce ERROR and do not stop later cases. Known limitations have a distinct KNOWN_LIMITATION status and are not counted as unknown regressions.

`first_failed_layer` is the earliest failed comparison in execution order. It is explicitly an observed failure boundary, not a root-cause claim.

State supports exact values, presence, absence/None, and case-insensitive semantic cue matching. Workflow checks Stage, optional next action, and the exact allowed-tool set when specified. Retrieval checks source inclusion without requiring rank order. Vision checks invocation, observation presence, and updated fields. Tool evaluation reads actual `tool_calls`, separately from allowed tools. Answer evaluation uses case-insensitive required and forbidden phrases without exact-answer matching.

## CLI

```bash
.venv/bin/python -m evaluation.cli --case case_08
.venv/bin/python -m evaluation.cli --category retrieval
.venv/bin/python -m evaluation.cli --all
.venv/bin/python -m evaluation.cli --all --json evaluation_results.json
```

## Live execution status

The implementation environment did not expose `DEEPSEEK_API_KEY` or `DASHSCOPE_API_KEY`, so the real 15-case suite was not run. No live result was fabricated. Deterministic unit tests exercise execution, isolation, comparison, error continuation, and reporting without provider calls.
