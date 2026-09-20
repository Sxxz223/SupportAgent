"""Regression coverage for repository-backed runtime data sources."""
import asyncio
import contextlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import main  # Initialize project/SDK import separation.
from agents.tool_context import ToolContext

from support_agents.support_agent import create_support_agent
from application import turn_processor as processor
from application.context import AppContext
from application.session import SupportSession, TurnContext
from context.builder import build_model_context
from rag.retriever import search_knowledge
from repositories.demo_customer_repository import DemoCustomerRepository
from schemas.state import StateUpdate, SupportState
from tools.support_tools import get_owned_products, verify_customer


def invoke_tool(tool, session, arguments):
    context = ToolContext(
        context=AppContext(session=session),
        tool_name=tool.name,
        tool_call_id="data-source-get-product",
        tool_arguments=json.dumps(arguments),
    )
    return asyncio.run(tool.on_invoke_tool(
        context,
        json.dumps(arguments),
    ))


class DataSourceCleanupTests(unittest.TestCase):
    def test_unknown_bob_lookup_keeps_product_unknown_and_stage_verify_identity(self):
        session = SupportSession()

        def run(agent, _text, *, context):
            self.assertIn("product: unknown", agent.instructions)
            payload = json.loads(invoke_tool(
                verify_customer, context.session, {"phone_last4": "9999"}
            ))
            self.assertFalse(payload["verified"])
            return SimpleNamespace(final_output="Please tell me your product model.")

        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=StateUpdate(user_name="Bob")), \
             patch.object(processor.Runner, "run_sync", side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            response = processor.process_turn(session, "I'm Bob.")

        self.assertEqual(response, "Please tell me your product model.")
        self.assertEqual(session.state.user_name, "Bob")
        self.assertIsNone(session.state.product)
        self.assertEqual(session.state.stage, "verify_identity")
        self.assertEqual(session.events[-1].event_type, "identity_verification_failed")
        self.assertNotIn("Anker Prime Charger (250W, 6 Ports, GaNPrime)", response)

    def test_configured_alice_lookup_updates_product_from_repository(self):
        session = SupportSession()
        session.state.user_name = "Alice"
        invoke_tool(verify_customer, session, {"phone_last4": "3721"})

        payload = json.loads(invoke_tool(
            get_owned_products, session, {"customer_id": session.state.customer_id}
        ))

        self.assertTrue(payload["found"])
        self.assertEqual(payload["products"][0]["model"], "A2345")
        self.assertEqual(payload["products"][0]["product_id"], "anker-prime-250w")
        self.assertEqual(session.state.product, "Anker Prime Charger (250W, 6 Ports, GaNPrime)")
        self.assertEqual(session.state.product_id, "anker-prime-250w")
        self.assertEqual(session.events[-1].event_type, "product_lookup_succeeded")

    def test_unconfirmed_lookup_does_not_overwrite_user_provided_product(self):
        session = SupportSession()
        session.state.user_name = "Jack"
        session.state.product = "M1 Pro"

        payload = json.loads(invoke_tool(
            verify_customer, session, {"phone_last4": "9999"}
        ))

        self.assertEqual(payload["status"], "NOT_FOUND")
        self.assertFalse(payload["verified"])
        self.assertEqual(session.state.product, "M1 Pro")
        self.assertFalse(session.state.identity_verified)
        self.assertEqual(session.events[-1].event_type, "identity_verification_failed")

    def test_unknown_lookup_never_records_false_success_event(self):
        session = SupportSession()
        session.state.user_name = "Unknown User"

        payload = json.loads(invoke_tool(
            verify_customer, session, {"phone_last4": "9999"}
        ))

        self.assertFalse(payload["verified"])
        self.assertIsNone(session.state.product)
        event_types = [event.event_type for event in session.events]
        self.assertEqual(event_types, ["identity_verification_failed"])
        self.assertNotIn("product_lookup_succeeded", event_types)

    def test_demo_repository_has_no_name_based_product_lookup(self):
        repository = DemoCustomerRepository()
        self.assertFalse(hasattr(repository, "get_products_for_user"))

    def test_context_and_prompt_do_not_turn_rag_into_ownership_evidence(self):
        state = SupportState()
        context = build_model_context(
            state,
            TurnContext(user_input="What product do I own?"),
            [],
            [],
        )
        agent = create_support_agent(context, "model", [])

        self.assertIn("product: unknown", context)
        self.assertNotIn("your Anker Prime Charger (250W, 6 Ports, GaNPrime)", context)
        self.assertIn("RAG knowledge describes products", agent.instructions)
        self.assertIn("ownership lookup succeeds after identity verification", agent.instructions)

    def test_product_knowledge_is_not_returned_for_an_unknown_product(self):
        class Encoder:
            def encode(self, _text):
                return [1.0, 0.0]

        result = search_knowledge(
            "M1 Pro will not charge",
            Encoder(),
            product="M1 Pro",
        )

        self.assertEqual(result, "")
        self.assertNotIn("Anker Prime Charger (250W, 6 Ports, GaNPrime)", result)


if __name__ == "__main__":
    unittest.main()
