"""Regression coverage for structured per-turn execution traces."""
import asyncio
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import main as entry
from agents.tool_context import ToolContext

from application import turn_processor as processor
from application.context import AppContext
from application.session import SupportSession
from schemas.state import StateUpdate
from schemas.vision import VisionUpdate
from tools.support_tools import check_warranty, create_ticket, verify_customer
from trace.recorder import format_trace


RAG_RESULT = """[Score: 0.820]
[Source: anker_prime_250w/charging_power.md]
Clean the charging contacts and reseat the robot.

[Score: 0.690]
[Source: anker_prime_250w/overview.md]
The dock indicator should be on while charging."""


def invoke(tool, session, arguments):
    context = ToolContext(
        context=AppContext(session=session),
        tool_name=tool.name,
        tool_call_id=f"trace-{tool.name}",
        tool_arguments=json.dumps(arguments),
    )
    return asyncio.run(tool.on_invoke_tool(context, json.dumps(arguments)))


class TurnTraceTests(unittest.TestCase):
    def run_turn(
        self,
        session,
        text,
        *,
        update=None,
        image_path=None,
        vision=None,
        runner=None,
        retrieval=RAG_RESULT,
    ):
        update = update or StateUpdate()
        runner = runner or (lambda *_args, **_kwargs: SimpleNamespace(final_output="Final answer"))
        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=update), \
             patch.object(processor, "create_qwen_client", return_value="qwen"), \
             patch.object(processor, "analyze_image_qwen", return_value=vision), \
             patch.object(processor, "create_embedding_model", return_value="embedding"), \
             patch.object(processor, "search_knowledge", return_value=retrieval), \
             patch.object(processor.Runner, "run_sync", side_effect=runner), \
             contextlib.redirect_stdout(io.StringIO()):
            return processor.process_turn(session, text, image_path)

    def test_text_turn_records_input_extraction_state_stage_and_answer(self):
        session = SupportSession()

        answer = self.run_turn(session, "I'm Alice.", update=StateUpdate(user_name="Alice"))

        self.assertEqual(answer, "Final answer")
        self.assertEqual(len(session.traces), 1)
        trace = session.traces[0]
        self.assertEqual(trace.user_input, "I'm Alice.")
        self.assertFalse(trace.has_image)
        self.assertIsNone(trace.state_before["user_name"])
        self.assertEqual(trace.extraction_result["user_name"], "Alice")
        self.assertEqual(trace.state_after_perception["user_name"], "Alice")
        self.assertEqual(trace.workflow_before_agent.stage, "verify_identity")
        self.assertEqual(trace.final_answer, "Final answer")
        self.assertTrue(trace.context_built)
        self.assertTrue(trace.agent_called)
        self.assertIsNotNone(trace.finished_at)
        self.assertIsNotNone(trace.duration_ms)
        self.assertEqual(trace.tool_calls, [])

    def test_multiple_turns_create_independent_traces(self):
        session = SupportSession()
        self.run_turn(session, "I'm Alice.", update=StateUpdate(user_name="Alice"))
        self.run_turn(session, "My product is Anker Prime Charger (250W, 6 Ports, GaNPrime).", update=StateUpdate(product="Anker Prime Charger (250W, 6 Ports, GaNPrime)"))

        self.assertEqual([trace.turn_index for trace in session.traces], [1, 2])
        self.assertNotEqual(session.traces[0].trace_id, session.traces[1].trace_id)
        self.assertIsNone(session.traces[0].state_before["user_name"])
        self.assertEqual(session.traces[1].state_before["user_name"], "Alice")

    def test_diagnose_trace_contains_bounded_rag_metadata(self):
        session = SupportSession()
        session.state.customer_id = "00000000-0000-0000-0000-000000000001"
        session.state.identity_verified = True
        self.run_turn(
            session,
            "My Anker Prime Charger (250W, 6 Ports, GaNPrime) won't charge.",
            update=StateUpdate(user_name="Alice", product="Anker Prime Charger (250W, 6 Ports, GaNPrime)", issue="won't charge"),
        )

        trace = session.traces[-1]
        self.assertEqual(trace.rag_query, "Anker Prime Charger (250W, 6 Ports, GaNPrime) won't charge")
        self.assertEqual(
            [(chunk.source, chunk.score) for chunk in trace.retrieved_chunks],
            [("anker_prime_250w/charging_power.md", 0.82), ("anker_prime_250w/overview.md", 0.69)],
        )
        self.assertLessEqual(len(trace.retrieved_chunks[0].preview), 180)
        self.assertNotIn("embedding", repr(trace.retrieved_chunks))

    def test_vision_trace_records_summary_and_changed_fields_without_image_data(self):
        session = SupportSession()
        session.state.customer_id = "00000000-0000-0000-0000-000000000001"
        session.state.identity_verified = True
        image = str(Path(entry.__file__).parent / "test_images" / "charging_contacts.png")
        self.run_turn(
            session,
            "Check this.",
            update=StateUpdate(user_name="Alice", product="Anker Prime Charger (250W, 6 Ports, GaNPrime)", issue="won't charge"),
            image_path=image,
            vision=VisionUpdate(
                indicator_on=True,
                contacts_dirty=True,
                observation="Dirty contacts are visible.",
            ),
        )

        trace = session.traces[-1]
        self.assertTrue(trace.has_image)
        self.assertTrue(trace.vision.used)
        self.assertEqual(trace.vision.observation, "Dirty contacts are visible.")
        self.assertIn("contacts_dirty", trace.vision.updated_fields)
        self.assertIn("image_received", trace.vision.updated_fields)
        self.assertNotIn(image, repr(trace))
        self.assertNotIn("base64", repr(trace).lower())

    def test_tools_record_args_results_state_changes_and_final_ticket(self):
        session = SupportSession()
        session.state.customer_id = "00000000-0000-0000-0000-000000000001"
        session.state.identity_verified = True

        def run(agent, _text, *, context):
            names = [tool.name for tool in agent.tools]
            if "create_ticket" in names:
                invoke(check_warranty, context.session, {"product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"})
                invoke(create_ticket, context.session, {
                    "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)", "issue": "won't charge",
                })
            return SimpleNamespace(final_output="Warranty checked and ticket created.")

        self.run_turn(
            session,
            "Please check warranty and create a ticket.",
            update=StateUpdate(user_name="Alice", product="Anker Prime Charger (250W, 6 Ports, GaNPrime)", issue="won't charge"),
            runner=run,
        )

        trace = session.traces[-1]
        self.assertEqual([item.tool_name for item in trace.tool_calls], [
            "check_warranty", "create_ticket",
        ])
        warranty, ticket = trace.tool_calls
        self.assertTrue(warranty.success)
        self.assertEqual(warranty.arguments, {"product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"})
        self.assertTrue(json.loads(warranty.result_summary)["found"])
        self.assertIn("warranty_status", warranty.state_changed_fields)
        self.assertIn("ticket_id", ticket.state_changed_fields)
        self.assertIsNotNone(trace.final_state["ticket_id"])
        self.assertIn("warranty_lookup_succeeded", trace.runtime_events)
        self.assertIn("ticket_created", trace.runtime_events)

    def test_identity_verification_trace_separates_workflow_before_and_after_tool(self):
        session = SupportSession()

        def run(_agent, _text, *, context):
            invoke(verify_customer, context.session, {"phone_last4": "3721"})
            return SimpleNamespace(final_output="Your identity is verified.")

        self.run_turn(
            session,
            "I'm Alice. My phone ends in 3721.",
            update=StateUpdate(user_name="Alice", phone_last4="3721"),
            runner=run,
        )

        trace = session.traces[-1]
        self.assertEqual(trace.workflow_before_agent.stage, "verify_identity")
        self.assertIn("verify_customer", trace.workflow_before_agent.allowed_tools)
        self.assertEqual(trace.workflow_after_tools.stage, "identify_product")
        self.assertEqual(trace.workflow_after_tools.allowed_tools, ["get_owned_products"])
        self.assertTrue(trace.final_state["identity_verified"])
        self.assertIsNone(trace.final_state["product"])

    def test_error_finishes_trace_and_preserves_safe_failure_stage(self):
        session = SupportSession()
        secret = "sk-do-not-record-this"
        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=StateUpdate()), \
             patch.object(processor, "create_qwen_client", return_value="qwen"), \
             patch.object(processor, "analyze_image_qwen", side_effect=RuntimeError(
                 f"Vision unavailable for {secret}"
             )), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                processor.process_turn(session, "Look", "image.png")

        trace = session.traces[-1]
        self.assertEqual(trace.error.failed_stage, "vision")
        self.assertEqual(trace.error.error_type, "RuntimeError")
        self.assertNotIn(secret, trace.error.safe_error_message)
        self.assertIn("[redacted]", trace.error.safe_error_message)
        self.assertIsNotNone(trace.finished_at)

    def test_snapshots_do_not_change_with_later_state_mutation(self):
        session = SupportSession()
        self.run_turn(session, "I'm Alice.", update=StateUpdate(user_name="Alice"))
        trace = session.traces[-1]

        session.state.user_name = "Changed"
        session.state.attempted_steps.append("restart")

        self.assertIsNone(trace.state_before["user_name"])
        self.assertEqual(trace.final_state["user_name"], "Alice")
        self.assertEqual(trace.final_state["attempted_steps"], [])

    def test_trace_constructor_failure_does_not_fail_business_turn(self):
        session = SupportSession()
        with patch.object(processor, "TraceRecorder", side_effect=RuntimeError("trace failed")), \
             patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=StateUpdate(user_name="Alice")), \
             patch.object(processor.Runner, "run_sync", return_value=SimpleNamespace(final_output="ok")), \
             contextlib.redirect_stdout(io.StringIO()):
            answer = processor.process_turn(session, "I'm Alice.")

        self.assertEqual(answer, "ok")
        self.assertEqual(session.state.user_name, "Alice")

    def test_formatter_is_human_readable_and_does_not_include_prompt(self):
        session = SupportSession()
        self.run_turn(session, "I'm Alice.", update=StateUpdate(user_name="Alice"))

        output = format_trace(session.traces[-1])

        self.assertIn("TURN 1", output)
        self.assertIn("STATE BEFORE", output)
        self.assertIn("EXTRACTION", output)
        self.assertIn("WORKFLOW BEFORE AGENT", output)
        self.assertIn("WORKFLOW AFTER TOOLS", output)
        self.assertIn("FINAL ANSWER", output)
        self.assertIn("DURATION", output)
        self.assertNotIn("Current Business State:", output)


if __name__ == "__main__":
    unittest.main()
