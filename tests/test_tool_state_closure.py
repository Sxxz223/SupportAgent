"""Regression tests for Tool execution writing back to session state."""
import asyncio
import contextlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import main  # Initialize package import handling before importing the SDK.
from agents.tool_context import ToolContext

from my_project.application.context import AppContext
from my_project.application.session import SupportSession
from my_project.application import turn_processor as processor
from my_project.schemas.state import StateUpdate
from my_project.tools.support_tools import (
    check_warranty,
    create_ticket,
    get_owned_products,
    open_ticket,
    verify_customer,
)
from my_project.workflow.stages import get_allowed_tools


def invoke(tool, session, arguments):
    """Invoke a real SDK FunctionTool with the application's local context."""
    context = ToolContext(
        context=AppContext(session=session),
        tool_name=tool.name,
        tool_call_id=f"test-{tool.name}",
        tool_arguments=json.dumps(arguments),
    )
    return asyncio.run(tool.on_invoke_tool(context, json.dumps(arguments)))


class ToolStateClosureTests(unittest.TestCase):
    def test_verified_customer_product_lookup_updates_same_session_state(self):
        session = SupportSession()
        state_identity = id(session.state)
        session.state.user_name = "Alice"

        verification = invoke(verify_customer, session, {"phone_last4": "3721"})
        result = invoke(get_owned_products, session, {
            "customer_id": session.state.customer_id,
        })

        self.assertTrue(json.loads(verification)["verified"])
        self.assertTrue(json.loads(result)["found"])
        self.assertEqual(session.state.product, "Anker Prime Charger (250W, 6 Ports, GaNPrime)")
        self.assertEqual(session.state.customer_id, "00000000-0000-0000-0000-000000000001")
        self.assertTrue(session.state.identity_verified)
        self.assertEqual(id(session.state), state_identity)
        self.assertEqual(session.events[-1].event_type, "product_lookup_succeeded")

    def test_check_warranty_updates_status(self):
        session = SupportSession()
        session.state.user_name = "Alice"
        session.state.customer_id = "00000000-0000-0000-0000-000000000001"
        session.state.identity_verified = True

        result = invoke(check_warranty, session, {"product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"})

        self.assertEqual(json.loads(result)["expires_at"], "2027-08-01")
        self.assertEqual(session.state.warranty_status, "active")
        self.assertEqual(session.events[-1].event_type, "warranty_lookup_succeeded")

    def test_create_ticket_updates_id(self):
        session = SupportSession()

        result = invoke(create_ticket, session, {
            "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)",
            "issue": "won't charge",
        })

        payload = json.loads(result)
        self.assertTrue(payload["created"])
        self.assertEqual(session.state.ticket_id, payload["ticket_id"])
        self.assertEqual(session.events[-1].event_type, "ticket_created")

        duplicate = invoke(create_ticket, session, {
            "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)",
            "issue": "won't charge",
        })
        self.assertTrue(json.loads(duplicate)["already_exists"])
        self.assertEqual(
            [event.event_type for event in session.events].count("ticket_created"),
            1,
        )

    def test_duplicate_ticket_is_idempotent_and_permission_is_removed(self):
        session = SupportSession()
        session.state.user_name = "Alice"
        session.state.customer_id = "00000000-0000-0000-0000-000000000001"
        session.state.identity_verified = True
        session.state.stage = "diagnose"
        first = open_ticket(session.state, "Anker Prime Charger (250W, 6 Ports, GaNPrime)", "won't charge")
        original_id = session.state.ticket_id

        second = open_ticket(session.state, "Different product", "Different issue")
        tools, names = get_allowed_tools(session.state)

        self.assertTrue(json.loads(first)["created"])
        self.assertEqual(json.loads(second)["ticket_id"], original_id)
        self.assertEqual(session.state.ticket_id, original_id)
        self.assertNotIn("create_ticket", names)
        self.assertNotIn(create_ticket, tools)
        self.assertEqual(names, ["check_warranty"])

    def test_ticket_created_in_one_turn_affects_the_next_turn(self):
        session = SupportSession()
        session.state.user_name = "Alice"
        session.state.customer_id = "00000000-0000-0000-0000-000000000001"
        session.state.identity_verified = True
        session.state.product = "Anker Prime Charger (250W, 6 Ports, GaNPrime)"
        session.state.issue = "won't charge"
        state_identity = id(session.state)
        agents = []

        def run(agent, _text, *, context):
            self.assertIs(context.session, session)
            agents.append(agent)
            if len(agents) == 1:
                self.assertIn("create_ticket", [tool.name for tool in agent.tools])
                invoke(create_ticket, context.session, {
                    "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)",
                    "issue": "won't charge",
                })
            return SimpleNamespace(final_output=f"response-{len(agents)}")

        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=StateUpdate()), \
             patch.object(processor, "create_embedding_model", return_value="embedding"), \
             patch.object(processor, "search_knowledge", return_value="knowledge"), \
             patch.object(processor.Runner, "run_sync", side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            processor.process_turn(session, "Please create a repair ticket.")
            processor.process_turn(session, "What is my ticket status?")

        self.assertEqual(id(session.state), state_identity)
        self.assertIsNotNone(session.state.ticket_id)
        self.assertEqual(session.state.stage, "diagnose")
        self.assertNotIn("create_ticket", [tool.name for tool in agents[1].tools])
        self.assertIn(f"ticket_id: {session.state.ticket_id}", agents[1].instructions)
        self.assertEqual(session.turn_index, 2)
        self.assertEqual(len(session.history), 4)

    def test_process_turn_recomputes_stage_after_product_tool(self):
        session = SupportSession()
        session.state.user_name = "Alice"
        session.state.customer_id = "00000000-0000-0000-0000-000000000001"
        session.state.identity_verified = True

        def run(agent, _text, *, context):
            names = [tool.name for tool in agent.tools]
            if names:
                self.assertEqual(names, ["get_owned_products"])
                invoke(get_owned_products, context.session, {
                    "customer_id": context.session.state.customer_id,
                })
            else:
                self.assertEqual(context.session.state.stage, "understand_issue")
            return SimpleNamespace(final_output="Product found.")

        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=StateUpdate()), \
             patch.object(processor.Runner, "run_sync", side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            processor.process_turn(session, "Which product do I own?")

        self.assertEqual(session.state.product, "Anker Prime Charger (250W, 6 Ports, GaNPrime)")
        self.assertEqual(session.state.stage, "understand_issue")


if __name__ == "__main__":
    unittest.main()
