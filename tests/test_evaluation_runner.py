"""Deterministic tests for the T7.3 runner, evaluators, and reports."""
from dataclasses import asdict
import json
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

import main  # Initialize project/SDK import separation.

from my_project.application.session import SupportSession
from my_project.evaluation import get_case
from my_project.evaluation.evaluators import evaluate_case
from my_project.evaluation.models import (
    AnswerRequirements,
    EvaluationCase,
    EvaluationExpectations,
    EvaluationTurn,
    FieldExpectation,
)
from my_project.evaluation.report import format_suite_report, suite_to_json, write_json_report
from my_project.evaluation.runner import EvaluationRunner
from my_project.trace.models import (
    RetrievalChunkTrace, ToolCallTrace, TurnTrace, VisionTrace, WorkflowTrace,
)


def make_case(
    *,
    case_id="test_case",
    category="workflow",
    turns=(EvaluationTurn("hello"),),
    expectations=None,
    initial_state=None,
    expected_pass=True,
    known_limitation=False,
):
    return EvaluationCase(
        id=case_id,
        name=case_id,
        category=category,
        description="deterministic fixture",
        turns=turns,
        expectations=expectations or EvaluationExpectations(),
        initial_state=initial_state or {},
        expected_pass=expected_pass,
        known_limitation=known_limitation,
        notes="known" if known_limitation else None,
    )


def make_trace(**overrides):
    values = {
        "trace_id": "trace-1",
        "turn_index": 1,
        "started_at": "2026-01-01T00:00:00+00:00",
        "user_input": "hello",
        "has_image": False,
        "extraction_result": {},
        "state_after_perception": {},
        "workflow_before_agent": WorkflowTrace(
            stage="identify_user", next_action="continue_diagnosis", allowed_tools=[]
        ),
        "workflow_after_tools": WorkflowTrace(
            stage="identify_user", next_action="continue_diagnosis", allowed_tools=[]
        ),
        "final_state": {"stage": "identify_user"},
        "final_stage": "identify_user",
        "final_answer": "How can I help?",
    }
    values.update(overrides)
    return TurnTrace(**values)


class EvaluationRunnerTests(unittest.TestCase):
    def test_name_only_case_requires_verification_without_product_disclosure(self):
        trace = make_trace(
            extraction_result={"user_name": "Alice", "product": None, "issue": None},
            final_state={
                "user_name": "Alice",
                "customer_id": None, "identity_verified": False,
                "product": None, "product_id": None,
                "stage": "verify_identity",
            },
            final_stage="verify_identity",
            workflow_before_agent=WorkflowTrace(
                "verify_identity", "verify_identity", ["verify_customer"]
            ),
            workflow_after_tools=WorkflowTrace(
                "verify_identity", "verify_identity", ["verify_customer"]
            ),
            tool_calls=[],
        )

        result = evaluate_case(get_case("case_01"), [trace])

        self.assertEqual(result.status, "PASS")

    def test_unknown_customer_case_keeps_product_unknown(self):
        trace = make_trace(
            extraction_result={"user_name": "Bob", "product": None, "issue": None},
            final_state={
                "user_name": "Bob", "product": None, "product_id": None,
                "stage": "verify_identity",
            },
            final_stage="verify_identity",
            final_answer="Please provide the last four phone digits or an order number.",
            workflow_before_agent=WorkflowTrace(
                "verify_identity", "verify_identity", ["verify_customer"]
            ),
            workflow_after_tools=WorkflowTrace(
                "verify_identity", "verify_identity", ["verify_customer"]
            ),
            tool_calls=[],
        )

        result = evaluate_case(get_case("case_unknown_customer_product"), [trace])

        self.assertEqual(result.status, "PASS")

    def test_single_turn_runner_uses_process_turn_and_trace(self):
        def process(*, session, user_input, image_path):
            self.assertIsNone(image_path)
            session.turn_index += 1
            session.state.user_name = "Alice"
            session.state.stage = "identify_product"
            session.traces.append(make_trace(
                user_input=user_input,
                extraction_result={"user_name": "Alice", "product": None, "issue": None},
                workflow_before_agent=WorkflowTrace(
                    "identify_product", "identify_product", ["get_product"]
                ),
                workflow_after_tools=WorkflowTrace(
                    "identify_product", "identify_product", ["get_product"]
                ),
                final_stage="identify_product",
                final_state={"user_name": "Alice", "stage": "identify_product"},
                final_answer="Hello Alice.",
            ))
            return "Hello Alice."

        case = make_case(
            category="extraction",
            expectations=EvaluationExpectations(
                expected_state={"user_name": "Alice"},
                expected_stage="identify_product",
            ),
        )
        result = EvaluationRunner(process_turn_fn=process).run_case(case)

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.turn_count, 1)
        self.assertEqual(result.trace_ids, ["trace-1"])

    def test_multi_turn_runner_reuses_one_session(self):
        seen = []

        def process(*, session, user_input, image_path):
            seen.append(session)
            session.turn_index += 1
            if session.turn_index == 1:
                session.state.user_name = "Alice"
            elif session.turn_index == 2:
                self.assertEqual(session.state.user_name, "Alice")
                session.state.product = "Anker Prime Charger (250W, 6 Ports, GaNPrime)"
            else:
                self.assertEqual(session.state.product, "Anker Prime Charger (250W, 6 Ports, GaNPrime)")
                session.state.issue = "receiving power"
                session.state.stage = "diagnose"
            session.traces.append(make_trace(
                trace_id=f"trace-{session.turn_index}",
                turn_index=session.turn_index,
                user_input=user_input,
                workflow_before_agent=WorkflowTrace(
                    session.state.stage, "continue_diagnosis", []
                ),
                workflow_after_tools=WorkflowTrace(
                    session.state.stage, "continue_diagnosis", []
                ),
                final_stage=session.state.stage,
                final_state=asdict(session.state),
            ))
            return "ok"

        case = make_case(
            category="multi_turn",
            turns=(EvaluationTurn("one"), EvaluationTurn("two"), EvaluationTurn("three")),
            expectations=EvaluationExpectations(
                expected_state={"user_name": "Alice", "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"},
                expected_state_fields={
                    "issue": FieldExpectation(contains_any=("receiving power",)),
                },
                expected_stage="diagnose",
            ),
        )
        result = EvaluationRunner(process_turn_fn=process).run_case(case)

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.turn_count, 3)
        self.assertTrue(all(session is seen[0] for session in seen))

    def test_different_cases_use_isolated_sessions(self):
        sessions = []

        def process(*, session, user_input, image_path):
            sessions.append(session)
            self.assertEqual(session.history, [])
            session.history.append({"role": "user", "content": user_input})
            session.turn_index += 1
            session.traces.append(make_trace(trace_id=f"trace-{len(sessions)}"))
            return "ok"

        runner = EvaluationRunner(process_turn_fn=process)
        suite = runner.run([make_case(case_id="a"), make_case(case_id="b")])

        self.assertEqual(suite.total, 2)
        self.assertIsNot(sessions[0], sessions[1])
        self.assertIsNot(sessions[0].state, sessions[1].state)
        self.assertIsNot(sessions[0].traces, sessions[1].traces)

    def test_state_exact_contains_present_and_absent_comparison(self):
        case = make_case(expectations=EvaluationExpectations(
            expected_state={"user_name": "Alice"},
            expected_state_fields={
                "issue": FieldExpectation(contains_any=("charging",)),
                "ticket_id": FieldExpectation(must_be_present=True),
                "warranty_status": FieldExpectation(must_be_absent=True),
            },
        ))
        trace = make_trace(final_state={
            "user_name": "Alice", "issue": "charging problem",
            "ticket_id": "A001", "warranty_status": None,
        })

        result = evaluate_case(case, [trace])

        self.assertTrue(next(check for check in result.checks if check.layer == "state").passed)

    def test_workflow_compares_final_stage_separately_from_pre_agent_permissions(self):
        case = make_case(expectations=EvaluationExpectations(
            expected_stage="understand_issue",
            expected_next_action_before_agent="identify_product",
            expected_allowed_tools_before_agent=("get_product",),
        ))
        trace = make_trace(
            final_stage="understand_issue",
            workflow_before_agent=WorkflowTrace(
                "identify_product", "identify_product", ["get_product"]
            ),
            workflow_after_tools=WorkflowTrace(
                "understand_issue", "understand_issue", []
            ),
        )

        result = evaluate_case(case, [trace])

        check = next(check for check in result.checks if check.layer == "workflow")
        self.assertTrue(check.passed)
        self.assertEqual(check.actual["final_stage"], "understand_issue")
        self.assertEqual(check.actual["before_agent"]["allowed_tools"], ["get_product"])

    def test_retrieval_sources_ignore_order_and_extra_results(self):
        case = make_case(expectations=EvaluationExpectations(
            expected_rag_sources=("anker_prime_250w/charging_power.md",),
        ))
        trace = make_trace(retrieved_chunks=[
            RetrievalChunkTrace("anker_prime_250w/overview.md", 0.9),
            RetrievalChunkTrace("anker_prime_250w/charging_power.md", 0.8),
        ])

        result = evaluate_case(case, [trace])

        self.assertTrue(next(check for check in result.checks if check.layer == "retrieval").passed)

    def test_required_tool_must_be_actually_called(self):
        case = make_case(expectations=EvaluationExpectations(
            expected_tool_calls=("create_ticket",),
        ))
        failed = evaluate_case(case, [make_trace()])
        passed = evaluate_case(case, [make_trace(tool_calls=[
            ToolCallTrace("create_ticket", success=True),
        ])])

        self.assertFalse(next(check for check in failed.checks if check.layer == "tool").passed)
        self.assertTrue(next(check for check in passed.checks if check.layer == "tool").passed)

    def test_forbidden_tool_fails_when_actually_called(self):
        case = make_case(expectations=EvaluationExpectations(
            forbidden_tools=("create_ticket",),
        ))
        result = evaluate_case(case, [make_trace(tool_calls=[
            ToolCallTrace("create_ticket", success=True),
        ])])

        check = next(check for check in result.checks if check.layer == "tool")
        self.assertFalse(check.passed)
        self.assertIn("forbidden tools called", check.message)

    def test_vision_requires_call_observation_and_updated_fields(self):
        case = make_case(expectations=EvaluationExpectations(
            vision_used=True,
            expected_vision_fields=("contacts_dirty",),
        ))
        trace = make_trace(
            has_image=True,
            vision=VisionTrace(
                used=True,
                observation="Dirty contacts.",
                updated_fields=["image_received", "contacts_dirty"],
            ),
        )

        result = evaluate_case(case, [trace])

        self.assertTrue(next(check for check in result.checks if check.layer == "vision").passed)

    def test_answer_requirements_are_case_insensitive(self):
        case = make_case(expectations=EvaluationExpectations(
            answer_requirements=AnswerRequirements(
                must_mention=("charging contacts",),
                must_not_mention=("secret",),
                must_not_claim=("can make coffee",),
            ),
        ))
        result = evaluate_case(case, [make_trace(
            final_answer="Please clean the CHARGING CONTACTS first.",
        )])

        self.assertTrue(next(check for check in result.checks if check.layer == "answer").passed)

    def test_first_failed_layer_uses_execution_order_not_check_count(self):
        case = make_case(expectations=EvaluationExpectations(
            expected_state={"user_name": "Alice"},
            expected_stage="diagnose",
            expected_rag_sources=("missing.md",),
        ))
        result = evaluate_case(case, [make_trace(
            final_state={"user_name": "Bob"},
            final_stage="identify_user",
        )])

        self.assertEqual(result.first_failed_layer, "state")
        self.assertEqual(result.status, "FAIL")

    def test_known_limitation_is_separate_from_unknown_failure(self):
        case = make_case(
            expected_pass=False,
            known_limitation=True,
            expectations=EvaluationExpectations(expected_state={"product": "M1 Pro"}),
        )
        result = evaluate_case(case, [make_trace(final_state={"product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"})])

        self.assertEqual(result.status, "KNOWN_LIMITATION")
        self.assertFalse(result.passed)

    def test_json_report_serializes_without_full_traces(self):
        suite = EvaluationRunner(
            process_turn_fn=lambda **kwargs: kwargs["session"].traces.append(make_trace()) or "ok"
        ).run([make_case()])
        rendered = suite_to_json(suite)
        payload = json.loads(rendered)

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["case_results"][0]["trace_ids"], ["trace-1"])
        self.assertNotIn("state_before", rendered)
        with TemporaryDirectory() as directory:
            path = write_json_report(suite, Path(directory) / "results.json")
            self.assertEqual(json.loads(path.read_text())["total"], 1)

    def test_case_error_does_not_stop_suite(self):
        def process(*, session, user_input, image_path):
            if user_input == "fail":
                raise TimeoutError("provider timeout sk-private")
            session.traces.append(make_trace(trace_id="successful-trace"))
            return "ok"

        suite = EvaluationRunner(process_turn_fn=process).run([
            make_case(case_id="bad", turns=(EvaluationTurn("fail"),)),
            make_case(case_id="good", turns=(EvaluationTurn("pass"),)),
        ])

        self.assertEqual([result.status for result in suite.case_results], ["ERROR", "PASS"])
        self.assertEqual(suite.errors, 1)
        self.assertNotIn("sk-private", suite.case_results[0].error)
        self.assertIn("[redacted]", suite.case_results[0].error)

    def test_missing_trace_field_returns_clear_failure(self):
        case = make_case(expectations=EvaluationExpectations(
            expected_state={"user_name": "Alice"},
        ))
        trace = make_trace()
        trace.final_state = None

        result = evaluate_case(case, [trace])

        check = next(check for check in result.checks if check.layer == "state")
        self.assertFalse(check.passed)
        self.assertIn("missing final_state", check.message)

    def test_human_report_contains_summary_layers_and_first_failure(self):
        case = make_case(expectations=EvaluationExpectations(expected_stage="diagnose"))
        suite = EvaluationRunner(
            process_turn_fn=lambda **kwargs: kwargs["session"].traces.append(make_trace()) or "ok"
        ).run([case])

        report = format_suite_report(suite)

        self.assertIn("Agent Evaluation", report)
        self.assertIn("Workflow", report)
        self.assertIn("First observed failed layer: workflow", report)


if __name__ == "__main__":
    unittest.main()
