"""Deterministic comparisons between Evaluation expectations and TurnTrace facts."""
from typing import Any

from .models import (
    CaseResult,
    CheckResult,
    EVALUATION_LAYERS,
    EvaluationCase,
    FieldExpectation,
)
from trace.models import TurnTrace


def _pass(name: str, layer: str, expected: Any, actual: Any, message: str = "") -> CheckResult:
    return CheckResult(name, layer, True, "PASS", expected, actual, message)


def _fail(name: str, layer: str, expected: Any, actual: Any, message: str) -> CheckResult:
    return CheckResult(name, layer, False, "FAIL", expected, actual, message)


def _skip(layer: str) -> CheckResult:
    return CheckResult(
        name=f"{layer}_requirements",
        layer=layer,
        passed=None,
        status="SKIP",
        message="No expectation is defined for this layer.",
    )


def _last_trace(traces: list[TurnTrace]) -> TurnTrace | None:
    return traces[-1] if traces else None


def _match_field(actual: Any, expectation: FieldExpectation) -> tuple[bool, str]:
    if expectation.must_be_absent and actual is not None:
        return False, "Expected the field to be absent or None."
    if expectation.must_be_present and (actual is None or actual == ""):
        return False, "Expected the field to be present."
    if expectation.equals is not None and actual != expectation.equals:
        return False, "Exact field value did not match."
    if expectation.contains_any:
        normalized = str(actual or "").casefold()
        if not any(term.casefold() in normalized for term in expectation.contains_any):
            return False, "Field did not contain any accepted semantic cue."
    return True, ""


def evaluate_extraction(case: EvaluationCase, traces: list[TurnTrace]) -> CheckResult:
    if case.category != "extraction":
        return _skip("extraction")
    trace = _last_trace(traces)
    if trace is None:
        return _fail("extraction_result", "extraction", "structured extraction", None, "No TurnTrace was produced.")
    actual = getattr(trace, "extraction_result", None)
    if not isinstance(actual, dict):
        return _fail("extraction_result", "extraction", "structured extraction", actual, "Trace is missing extraction_result.")

    expectations = case.expectations
    if expectations.expected_extraction or expectations.expected_extraction_fields:
        expected_exact = expectations.expected_extraction
        expected_fields = expectations.expected_extraction_fields
    else:
        expected_exact = {
            key: value for key, value in expectations.expected_state.items()
            if key in {"user_name", "product", "issue"}
        }
        expected_fields = {
            key: value for key, value in expectations.expected_state_fields.items()
            if key in {"user_name", "product", "issue"}
        }
    failures: list[str] = []
    for key, expected in expected_exact.items():
        if actual.get(key) != expected:
            failures.append(f"{key}: expected {expected!r}, got {actual.get(key)!r}")
    for key, expectation in expected_fields.items():
        matched, message = _match_field(actual.get(key), expectation)
        if not matched:
            failures.append(f"{key}: {message}")
    expected = {**expected_exact, **expected_fields}
    if failures:
        return _fail("extraction_result", "extraction", expected, actual, "; ".join(failures))
    return _pass("extraction_result", "extraction", expected, actual)


def evaluate_state(case: EvaluationCase, traces: list[TurnTrace]) -> CheckResult:
    expectations = case.expectations
    if not expectations.expected_state and not expectations.expected_state_fields:
        return _skip("state")
    trace = _last_trace(traces)
    actual = getattr(trace, "final_state", None) if trace else None
    if not isinstance(actual, dict):
        return _fail("final_state", "state", "state expectations", actual, "Trace is missing final_state.")

    failures: list[str] = []
    for key, expected in expectations.expected_state.items():
        if key not in actual:
            failures.append(f"{key}: missing from final_state")
        elif actual[key] != expected:
            failures.append(f"{key}: expected {expected!r}, got {actual[key]!r}")
    for key, expectation in expectations.expected_state_fields.items():
        if key not in actual:
            failures.append(f"{key}: missing from final_state")
            continue
        matched, message = _match_field(actual[key], expectation)
        if not matched:
            failures.append(f"{key}: {message}")
    expected = {
        "exact": expectations.expected_state,
        "field_requirements": expectations.expected_state_fields,
    }
    if failures:
        return _fail("final_state", "state", expected, actual, "; ".join(failures))
    return _pass("final_state", "state", expected, actual)


def evaluate_workflow(case: EvaluationCase, traces: list[TurnTrace]) -> CheckResult:
    expectations = case.expectations
    if (
        expectations.expected_stage is None
        and expectations.expected_next_action_before_agent is None
        and expectations.expected_allowed_tools_before_agent is None
    ):
        return _skip("workflow")
    trace = _last_trace(traces)
    if trace is None:
        return _fail("workflow", "workflow", "workflow expectations", None, "No TurnTrace was produced.")
    before = getattr(trace, "workflow_before_agent", None)
    after = getattr(trace, "workflow_after_tools", None)
    actual = {
        "final_stage": getattr(after, "stage", None) or getattr(trace, "final_stage", None),
        "before_agent": {
            "next_action": getattr(before, "next_action", None),
            "allowed_tools": list(getattr(before, "allowed_tools", []) or []),
        },
    }
    failures: list[str] = []
    if expectations.expected_stage is not None and actual["final_stage"] != expectations.expected_stage:
        failures.append(
            f"final_stage: expected {expectations.expected_stage!r}, got {actual['final_stage']!r}"
        )
    if (
        expectations.expected_next_action_before_agent is not None
        and actual["before_agent"]["next_action"]
        != expectations.expected_next_action_before_agent
    ):
        failures.append("next_action did not match")
    if (
        expectations.expected_allowed_tools_before_agent is not None
        and set(actual["before_agent"]["allowed_tools"])
        != set(expectations.expected_allowed_tools_before_agent)
    ):
        failures.append("allowed_tools did not match")
    expected = {
        "final_stage": expectations.expected_stage,
        "before_agent": {
            "next_action": expectations.expected_next_action_before_agent,
            "allowed_tools": (
                list(expectations.expected_allowed_tools_before_agent)
                if expectations.expected_allowed_tools_before_agent is not None else None
            ),
        },
    }
    if failures:
        return _fail("workflow", "workflow", expected, actual, "; ".join(failures))
    return _pass("workflow", "workflow", expected, actual)


def evaluate_retrieval(case: EvaluationCase, traces: list[TurnTrace]) -> CheckResult:
    expected = set(case.expectations.expected_rag_sources)
    if not expected:
        return _skip("retrieval")
    actual = {
        chunk.source
        for trace in traces
        for chunk in (getattr(trace, "retrieved_chunks", []) or [])
        if getattr(chunk, "source", None)
    }
    missing = expected - actual
    if missing:
        return _fail(
            "retrieval_sources", "retrieval", sorted(expected), sorted(actual),
            f"Missing expected sources: {', '.join(sorted(missing))}",
        )
    return _pass("retrieval_sources", "retrieval", sorted(expected), sorted(actual))


def evaluate_vision(case: EvaluationCase, traces: list[TurnTrace]) -> CheckResult:
    expectations = case.expectations
    if expectations.vision_used is None and not expectations.expected_vision_fields:
        return _skip("vision")
    used_traces = [
        trace for trace in traces
        if getattr(getattr(trace, "vision", None), "used", False)
    ]
    used = bool(used_traces)
    updated_fields = {
        field
        for trace in used_traces
        for field in (getattr(trace.vision, "updated_fields", []) or [])
    }
    observations = [
        trace.vision.observation for trace in used_traces
        if getattr(trace.vision, "observation", None)
    ]
    actual = {
        "used": used,
        "updated_fields": sorted(updated_fields),
        "has_observation": bool(observations),
    }
    failures: list[str] = []
    if expectations.vision_used is not None and used != expectations.vision_used:
        failures.append(f"vision used expected {expectations.vision_used}, got {used}")
    if expectations.vision_used is True and not observations:
        failures.append("vision observation is missing")
    missing = set(expectations.expected_vision_fields) - updated_fields
    if missing:
        failures.append(f"missing updated visual fields: {', '.join(sorted(missing))}")
    expected = {
        "used": expectations.vision_used,
        "updated_fields": list(expectations.expected_vision_fields),
        "observation": "present" if expectations.vision_used else None,
    }
    if failures:
        return _fail("vision", "vision", expected, actual, "; ".join(failures))
    return _pass("vision", "vision", expected, actual)


def evaluate_tools(case: EvaluationCase, traces: list[TurnTrace]) -> CheckResult:
    required = set(case.expectations.expected_tool_calls)
    forbidden = set(case.expectations.forbidden_tools)
    if not required and not forbidden:
        return _skip("tool")
    actual = [
        call.tool_name
        for trace in traces
        for call in (getattr(trace, "tool_calls", []) or [])
        if getattr(call, "tool_name", None)
    ]
    actual_set = set(actual)
    missing = required - actual_set
    prohibited = forbidden & actual_set
    failures = []
    if missing:
        failures.append(f"required tools not called: {', '.join(sorted(missing))}")
    if prohibited:
        failures.append(f"forbidden tools called: {', '.join(sorted(prohibited))}")
    expected = {"required": sorted(required), "forbidden": sorted(forbidden)}
    if failures:
        return _fail("tool_calls", "tool", expected, actual, "; ".join(failures))
    return _pass("tool_calls", "tool", expected, actual)


def evaluate_answer(case: EvaluationCase, traces: list[TurnTrace]) -> CheckResult:
    requirements = case.expectations.answer_requirements
    if not (requirements.must_mention or requirements.must_not_mention or requirements.must_not_claim):
        return _skip("answer")
    trace = _last_trace(traces)
    answer = getattr(trace, "final_answer", None) if trace else None
    if not isinstance(answer, str):
        return _fail("final_answer", "answer", requirements, answer, "Trace is missing final_answer.")
    normalized = answer.casefold()
    missing = [term for term in requirements.must_mention if term.casefold() not in normalized]
    prohibited = [
        term for term in (*requirements.must_not_mention, *requirements.must_not_claim)
        if term.casefold() in normalized
    ]
    failures = []
    if missing:
        failures.append(f"missing required phrases: {', '.join(missing)}")
    if prohibited:
        failures.append(f"contained forbidden claims: {', '.join(prohibited)}")
    expected = {
        "must_mention": list(requirements.must_mention),
        "must_not_mention": list(requirements.must_not_mention),
        "must_not_claim": list(requirements.must_not_claim),
    }
    if failures:
        return _fail("final_answer", "answer", expected, answer, "; ".join(failures))
    return _pass("final_answer", "answer", expected, answer)


def evaluate_case(
    case: EvaluationCase,
    traces: list[TurnTrace],
    *,
    error: str | None = None,
    duration_ms: float = 0.0,
) -> CaseResult:
    """Evaluate every layer in execution order and identify the first observed failure."""
    checks = [
        evaluate_extraction(case, traces),
        evaluate_state(case, traces),
        evaluate_workflow(case, traces),
        evaluate_retrieval(case, traces),
        evaluate_vision(case, traces),
        evaluate_tools(case, traces),
        evaluate_answer(case, traces),
    ]
    failed_layers = [check.layer for check in checks if check.passed is False]
    first_failed_layer = next(
        (layer for layer in EVALUATION_LAYERS if layer in failed_layers),
        None,
    )
    observed_pass = not failed_layers and error is None
    if error is not None:
        status = "ERROR"
        if first_failed_layer is None:
            failed_stage = next(
                (
                    getattr(getattr(trace, "error", None), "failed_stage", None)
                    for trace in reversed(traces)
                    if getattr(trace, "error", None) is not None
                ),
                None,
            )
            first_failed_layer = failed_stage or "execution"
    elif case.known_limitation or not case.expected_pass:
        status = "KNOWN_LIMITATION"
    else:
        status = "PASS" if observed_pass else "FAIL"
    return CaseResult(
        case_id=case.id,
        case_name=case.name,
        category=case.category,
        passed=observed_pass,
        expected_pass=case.expected_pass,
        known_limitation=case.known_limitation,
        status=status,
        checks=checks,
        turn_count=len(traces),
        first_failed_layer=first_failed_layer,
        error=error,
        trace_ids=[getattr(trace, "trace_id", "missing") for trace in traces],
        duration_ms=duration_ms,
    )
