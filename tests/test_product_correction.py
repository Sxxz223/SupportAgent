"""A product correction must invalidate product-specific stale state."""
import main
import unittest

from my_project.schemas.state import ExtractedFact, StateUpdate, SupportState
from my_project.workflow.stages import apply_update, next_stage


class ProductCorrectionTests(unittest.TestCase):
    def test_correction_clears_old_product_diagnosis_and_fulfilment(self):
        state = SupportState(
            user_name="Alice", customer_id="customer-1", identity_verified=True,
            product="Anker Prime Charger (250W, 6 Ports, GaNPrime)",
            product_id="anker-prime-250w", issue="charging slowly",
            attempted_steps=["changed cable"], diagnostic_facts={"current_port": "USB-C1"},
            warranty_status="active", ticket_id="ticket-1", image_received=True,
            indicator_on=True,
        )

        apply_update(state, StateUpdate(product="M1 Pro"))

        self.assertEqual(state.product, "M1 Pro")
        self.assertIsNone(state.product_id)
        self.assertIsNone(state.issue)
        self.assertEqual(state.diagnostic_facts, {})
        self.assertEqual(state.attempted_steps, [])
        self.assertIsNone(state.warranty_status)
        self.assertIsNone(state.ticket_id)
        self.assertFalse(state.image_received)
        self.assertEqual(next_stage(state), "understand_issue")

    def test_same_product_alias_does_not_reset_diagnosis(self):
        state = SupportState(
            product="Anker Prime Charger (250W, 6 Ports, GaNPrime)",
            product_id="anker-prime-250w", issue="charging slowly",
        )
        apply_update(state, StateUpdate(product="A2345"))
        self.assertEqual(state.issue, "charging slowly")


if __name__ == "__main__":
    unittest.main()
