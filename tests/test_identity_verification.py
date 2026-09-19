"""Security regression coverage for deterministic customer verification."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

import main  # Initialize package/SDK import separation.

from my_project.application.session import SupportSession
from my_project.application.session import TurnContext
from my_project.context.builder import build_model_context
from my_project.repositories.sqlite_customer_repository import SQLiteCustomerRepository
from my_project.schemas.state import StateUpdate, SupportState
from my_project.services.customer_service import CustomerService
from my_project.tools.support_tools import load_owned_products, verify_identity
from my_project.workflow.stages import apply_update, get_allowed_tools, next_stage


class IdentityVerificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        repository = SQLiteCustomerRepository(Path(self.directory.name) / "support.db")
        self.service = CustomerService(repository)
        self.customer = self.service.create_customer("紫薇", "1221")
        self.service.create_order(
            self.customer.customer_id,
            "SC-ZIWEI-001",
            "soundcore-liberty-4-nc",
            "2026-01-01",
            "2027-01-01",
        )

    def test_name_only_requires_verification_and_exposes_only_verify_tool(self):
        state = SupportState()
        apply_update(state, StateUpdate(user_name="紫薇"))
        state.stage = next_stage(state)
        _, names = get_allowed_tools(state)

        self.assertEqual(state.stage, "verify_identity")
        self.assertFalse(state.identity_verified)
        self.assertIsNone(state.customer_id)
        self.assertEqual(names, ["verify_customer"])
        self.assertNotIn("get_owned_products", names)
        self.assertNotIn("check_warranty", names)
        self.assertEqual(
            self.service.verify_customer(name="紫薇").status,
            "INSUFFICIENT",
        )

    def test_phone_verification_uses_persistent_name_and_advances_stage(self):
        state = SupportState(user_name="紫薇")
        apply_update(state, StateUpdate(phone_last4="1221"))
        result = json.loads(verify_identity(state, service=self.service))
        state.stage = next_stage(state)

        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(state.identity_verified)
        self.assertEqual(state.customer_id, self.customer.customer_id)
        self.assertEqual(state.stage, "identify_product")
        self.assertEqual(state.user_name, "紫薇")

    def test_wrong_phone_keeps_identity_unverified_without_products(self):
        state = SupportState(user_name="紫薇", phone_last4="9999")
        result = json.loads(verify_identity(state, service=self.service))
        state.stage = next_stage(state)

        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertFalse(state.identity_verified)
        self.assertIsNone(state.customer_id)
        self.assertEqual(state.stage, "verify_identity")
        self.assertNotIn("products", result)

    def test_order_number_verifies_only_when_it_belongs_to_named_customer(self):
        verified = self.service.verify_customer(name="紫薇", order_no="SC-ZIWEI-001")
        rejected = self.service.verify_customer(name="Other", order_no="SC-ZIWEI-001")

        self.assertTrue(verified.verified)
        self.assertEqual(verified.customer_id, self.customer.customer_id)
        self.assertEqual(rejected.status, "NOT_FOUND")

    def test_owned_products_requires_matching_verified_customer_id(self):
        unverified = SupportState(user_name="紫薇")
        denied = json.loads(load_owned_products(
            unverified, self.customer.customer_id, self.service
        ))
        self.assertEqual(denied["error"], "identity_not_verified")
        self.assertEqual(denied["products"], [])

        verified = SupportState(
            user_name="紫薇",
            customer_id=self.customer.customer_id,
            identity_verified=True,
        )
        allowed = json.loads(load_owned_products(
            verified, self.customer.customer_id, self.service
        ))
        self.assertTrue(allowed["found"])
        self.assertEqual(allowed["products"][0]["product_id"], "soundcore-liberty-4-nc")
        self.assertEqual(allowed["products"][0]["order_number"], "SC-ZIWEI-001")
        self.assertEqual(allowed["products"][0]["purchase_date"], "2026-01-01")
        self.assertEqual(allowed["products"][0]["warranty_until"], "2027-01-01")

        wrong_customer = json.loads(load_owned_products(verified, "other-id", self.service))
        self.assertEqual(wrong_customer["error"], "identity_not_verified")

    def test_owned_product_order_summary_reaches_model_context(self):
        state = SupportState(
            user_name="紫薇", customer_id=self.customer.customer_id, identity_verified=True,
        )
        load_owned_products(state, self.customer.customer_id, self.service)
        state.stage = next_stage(state)
        context = build_model_context(state, TurnContext("1221"), [], [])

        self.assertIn("soundcore Liberty 4 NC", context)
        self.assertIn("A3947", context)
        self.assertIn("SC-ZIWEI-001", context)
        self.assertIn("2026-01-01", context)
        self.assertIn("2027-01-01", context)

    def test_multiple_products_are_candidates_and_are_not_auto_selected(self):
        self.service.create_order(
            self.customer.customer_id, "SC-ZIWEI-002", "anker-nano-70w",
            "2026-02-01", "2027-02-01",
        )
        state = SupportState(
            user_name="紫薇", customer_id=self.customer.customer_id, identity_verified=True,
        )
        load_owned_products(state, self.customer.customer_id, self.service)
        state.stage = next_stage(state)

        self.assertEqual(len(state.owned_products), 2)
        self.assertIsNone(state.product)
        self.assertEqual(state.stage, "identify_product")
        self.assertEqual(get_allowed_tools(state)[1], [])

    def test_zero_products_are_recorded_without_invention(self):
        customer = self.service.create_customer("No Orders", "4000")
        state = SupportState(
            user_name="No Orders", customer_id=customer.customer_id, identity_verified=True,
        )
        result = json.loads(load_owned_products(state, customer.customer_id, self.service))
        state.stage = next_stage(state)

        self.assertFalse(result["found"])
        self.assertEqual(state.owned_products, [])
        self.assertIsNone(state.product)
        self.assertEqual(state.stage, "identify_product")
        self.assertEqual(get_allowed_tools(state)[1], [])

    def test_sessions_do_not_share_verified_identity(self):
        first = SupportSession()
        first.state.customer_id = self.customer.customer_id
        first.state.identity_verified = True
        second = SupportSession()

        self.assertFalse(second.state.identity_verified)
        self.assertIsNone(second.state.customer_id)

    def test_none_updates_preserve_name_and_verification_inputs(self):
        state = SupportState(user_name="紫薇")
        apply_update(state, StateUpdate(phone_last4="1221"))
        apply_update(state, StateUpdate(user_name=None, phone_last4=None))

        self.assertEqual(state.user_name, "紫薇")
        self.assertEqual(state.phone_last4, "1221")


if __name__ == "__main__":
    unittest.main()
