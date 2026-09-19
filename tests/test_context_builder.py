"""Tests for the controlled Program Data -> Model Context bridge."""
import asyncio
import json
import unittest

import main  # Initialize project/SDK import separation.
from agents.tool_context import ToolContext

from my_project.application.context import AppContext
from my_project.application.events import RuntimeEvent
from my_project.application.session import SupportSession, TurnContext
from my_project.context.builder import build_model_context
from my_project.schemas.state import SupportState
from my_project.schemas.vision import VisionUpdate
from my_project.tools.support_tools import (
    check_warranty, create_ticket, get_owned_products, verify_customer,
)


def invoke(tool, session, arguments):
    context = ToolContext(
        context=AppContext(session=session),
        tool_name=tool.name,
        tool_call_id=f"context-test-{tool.name}",
        tool_arguments=json.dumps(arguments),
    )
    return asyncio.run(tool.on_invoke_tool(context, json.dumps(arguments)))


class ContextBuilderTests(unittest.TestCase):
    def test_current_business_state_is_selected(self):
        state = SupportState(
            user_name="Alice",
            product="Anker Prime Charger (250W, 6 Ports, GaNPrime)",
            issue="won't charge",
            stage="diagnose",
            ticket_id="A001",
        )
        turn = TurnContext(user_input="What is the status?", next_action="continue_diagnosis")

        result = build_model_context(state, turn, [], [])

        self.assertIn("user_name: Alice", result)
        self.assertIn("product: Anker Prime Charger (250W, 6 Ports, GaNPrime)", result)
        self.assertIn("ticket_id: A001", result)
        self.assertIn("stage: diagnose", result)

    def test_ticket_event_is_one_compact_previous_action(self):
        state = SupportState(ticket_id="A001")
        events = [RuntimeEvent(
            event_type="ticket_created",
            turn_index=4,
            data={"ticket_id": "A001", "product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"},
        )]

        result = build_model_context(
            state,
            TurnContext(user_input="status"),
            events,
            [],
        )

        self.assertEqual(result.count("ticket_created"), 1)
        self.assertIn("turn 4: ticket_created", result)
        self.assertLessEqual(result.count("A001"), 2)  # Current fact + one causal event.

    def test_no_image_turn_labels_previous_observation_as_historical(self):
        events = [RuntimeEvent(
            event_type="vision_analyzed",
            turn_index=1,
            data={"observation": "Dirty contacts were visible."},
        )]

        result = build_model_context(
            SupportState(image_received=True, contacts_dirty=True),
            TurnContext(user_input="What now?"),
            events,
            [],
        )

        self.assertIn("no image was provided or analyzed in the current turn", result)
        self.assertIn("historical image observation from turn 1", result)
        self.assertIn("this was not observed in the current turn", result)
        self.assertIn("Dirty contacts were visible.", result)

    def test_current_image_is_current_turn_evidence(self):
        turn = TurnContext(
            user_input="Here is a photo.",
            image_path="photo.png",
            vision_update=VisionUpdate(
                indicator_on=True,
                contacts_dirty=True,
                observation="Current image shows dirty contacts.",
            ),
        )

        result = build_model_context(SupportState(), turn, [], [])

        self.assertIn("Current-turn Evidence:", result)
        self.assertIn("source: image analyzed in the current turn", result)
        self.assertIn("Current image shows dirty contacts.", result)
        self.assertNotIn("historical image observation from", result)

    def test_tool_updates_are_visible_in_next_model_context(self):
        session = SupportSession()
        session.turn_index = 1
        session.state.user_name = "Alice"
        session.state.phone_last4 = "3721"
        invoke(verify_customer, session, {"phone_last4": "3721"})
        invoke(get_owned_products, session, {"customer_id": session.state.customer_id})
        invoke(check_warranty, session, {"product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)"})
        invoke(create_ticket, session, {"product": "Anker Prime Charger (250W, 6 Ports, GaNPrime)", "issue": "won't charge"})

        result = build_model_context(
            session.state,
            TurnContext(user_input="What happened?"),
            session.events,
            session.history,
        )

        self.assertIn("product: Anker Prime Charger (250W, 6 Ports, GaNPrime)", result)
        self.assertIn("warranty_status: active", result)
        self.assertIn(f"ticket_id: {session.state.ticket_id}", result)
        self.assertIn("product_lookup_succeeded", result)
        self.assertIn("warranty_lookup_succeeded", result)
        self.assertIn("ticket_created", result)

    def test_local_context_and_unselected_runtime_data_are_not_serialized(self):
        session = SupportSession()
        session.state.internal_secret = "LOCAL_CONTEXT_SECRET"
        session.events.append(RuntimeEvent(
            event_type="debug_only",
            turn_index=1,
            data={"secret": "DEBUG_SECRET"},
        ))
        app_context = AppContext(session=session)

        result = build_model_context(
            session.state,
            TurnContext(user_input="hello"),
            session.events,
            session.history,
        )

        self.assertIs(app_context.session, session)
        self.assertNotIn("AppContext", result)
        self.assertNotIn("SupportSession", result)
        self.assertNotIn("LOCAL_CONTEXT_SECRET", result)
        self.assertNotIn("DEBUG_SECRET", result)
        self.assertNotIn("debug_only", result)


if __name__ == "__main__":
    unittest.main()
