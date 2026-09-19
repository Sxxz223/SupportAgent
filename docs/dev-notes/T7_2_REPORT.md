# T7.2 Fixed Evaluation Dataset

## Structure

- `evaluation/models.py` defines immutable `EvaluationTurn`, `FieldExpectation`, `AnswerRequirements`, `EvaluationExpectations`, and `EvaluationCase` records.
- `evaluation/cases.py` owns the fixed case tuple and portable image-fixture resolver.
- `evaluation/__init__.py` exposes the dataset API.

The dataset is declarative. It does not call `process_turn`, providers, Vision, embeddings, or the Main Agent. Automated execution and scoring remain reserved for T7.3.

## Dataset

The 15 fixed cases cover:

- extraction: 2
- workflow: 3
- multi-turn State continuity: 1
- semantic retrieval: 2
- Vision: 2
- Tool behavior: 3
- boundary behavior: 2

Case 15, product correction from legacy demo product (removed) to M1 Pro, is marked `known_limitation=True` and `expected_pass=False`. The dataset records the desired boundary without changing the extractor, workflow, context, or Agent prompt to force a pass.

## Expectations

Stable facts use exact structured expectations. Natural-language issue fields can use semantic term alternatives, and answers use small `must_mention` / `must_not_claim` cue sets. Tool permission (`expected_tools`) is separate from required invocation (`expected_tool_calls`), which avoids treating an Agent-permitted action as an unconditional call.

No case uses exact final-answer matching because multiple clear, correct support responses can express the same behavior with different wording.

Image fixture paths are project-relative and resolved only when a future runner executes a case.
