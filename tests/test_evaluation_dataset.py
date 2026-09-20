"""Structural tests for the fixed T7.2 evaluation dataset."""
from collections import Counter
from dataclasses import fields
import unittest

import main  # Initialize project/SDK import separation.

from evaluation import (
    EVALUATION_CASES,
    EvaluationCase,
    EvaluationExpectations,
    EvaluationTurn,
    VALID_CATEGORIES,
    get_case,
    resolve_image_path,
)
from schemas.state import SupportState


class EvaluationDatasetTests(unittest.TestCase):
    def test_dataset_has_at_least_fifteen_unique_stable_ids(self):
        ids = [case.id for case in EVALUATION_CASES]
        self.assertGreaterEqual(len(EVALUATION_CASES), 15)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue({"case_identity_phone", "case_identity_order", "case_identity_wrong_phone", "case_verified_owned_products"}.issubset(ids))

    def test_all_categories_are_valid_and_every_required_category_is_covered(self):
        counts = Counter(case.category for case in EVALUATION_CASES)
        self.assertEqual(set(counts), set(VALID_CATEGORIES))
        self.assertEqual(counts, {
            "extraction": 3,
            "workflow": 5,
            "multi_turn": 1,
            "retrieval": 3,
            "vision": 2,
            "tool": 4,
            "boundary": 3,
        })

    def test_turns_and_expectations_use_typed_schemas(self):
        for case in EVALUATION_CASES:
            with self.subTest(case=case.id):
                self.assertIsInstance(case, EvaluationCase)
                self.assertIsInstance(case.expectations, EvaluationExpectations)
                self.assertGreaterEqual(len(case.turns), 1)
                self.assertTrue(all(isinstance(turn, EvaluationTurn) for turn in case.turns))

    def test_initial_and_expected_state_fields_are_real_business_fields(self):
        state_fields = {item.name for item in fields(SupportState)}
        for case in EVALUATION_CASES:
            with self.subTest(case=case.id):
                self.assertLessEqual(set(case.initial_state), state_fields)
                self.assertLessEqual(set(case.expectations.expected_state), state_fields)
                self.assertLessEqual(set(case.expectations.expected_state_fields), state_fields)
                self.assertLessEqual(set(case.expectations.expected_extraction), state_fields)
                self.assertLessEqual(set(case.expectations.expected_extraction_fields), state_fields)

    def test_image_paths_are_portable_and_resolve_to_existing_fixtures(self):
        image_turns = [
            turn
            for case in EVALUATION_CASES
            for turn in case.turns
            if turn.image_path is not None
        ]
        self.assertEqual(len(image_turns), 2)
        for turn in image_turns:
            with self.subTest(image=turn.image_path):
                self.assertFalse(turn.image_path.startswith("/"))
                resolved = resolve_image_path(turn)
                self.assertTrue(resolved.is_file())
                self.assertEqual(resolved.suffix, ".png")

    def test_multi_turn_case_has_ordered_three_turn_conversation(self):
        case = get_case("case_06")
        self.assertEqual(case.category, "multi_turn")
        self.assertEqual(
            [turn.user_input for turn in case.turns],
            ["I'm Alice.", "I have an Anker Prime Charger (250W, 6 Ports, GaNPrime).", "It isn't receiving power."],
        )

    def test_expectations_cover_state_retrieval_vision_and_tool_boundaries(self):
        self.assertIn("anker_prime_250w/display_clock.md", get_case("case_07").expectations.expected_rag_sources)
        self.assertIn("anker_nano_70w/power_distribution.md", get_case("case_08").expectations.expected_rag_sources)
        self.assertIn("liberty_4_nc/pairing_reset.md", get_case("case_liberty_pairing").expectations.expected_rag_sources)
        self.assertTrue(get_case("case_09").expectations.vision_used)
        self.assertIn("create_ticket", get_case("case_12").expectations.expected_tool_calls)
        self.assertIn("create_ticket", get_case("case_13").expectations.forbidden_tools)
        self.assertTrue(get_case("case_10").expectations.expected_state_fields["contacts_dirty"].must_be_present)

    def test_known_and_unknown_customer_expectations_are_distinct(self):
        alice = get_case("case_01").expectations
        self.assertEqual(alice.expected_extraction, {"user_name": "Alice"})
        self.assertIsNone(alice.expected_state["product"])
        self.assertEqual(alice.expected_stage, "verify_identity")
        self.assertEqual(alice.expected_allowed_tools_before_agent, ("verify_customer",))

        bob = get_case("case_unknown_customer_product").expectations
        self.assertEqual(bob.expected_extraction, {"user_name": "Bob"})
        self.assertIsNone(bob.expected_state["product"])
        self.assertEqual(bob.expected_stage, "verify_identity")
        self.assertEqual(bob.expected_allowed_tools_before_agent, ("verify_customer",))

    def test_known_limitation_is_explicitly_expected_to_fail(self):
        limitations = [case for case in EVALUATION_CASES if case.known_limitation]
        self.assertEqual([case.id for case in limitations], ["case_15"])
        self.assertTrue(all(not case.expected_pass for case in limitations))
        self.assertTrue(all(case.notes for case in limitations))

    def test_answer_requirements_are_behavior_cues_not_exact_answers(self):
        expectation_fields = {item.name for item in fields(EvaluationExpectations)}
        self.assertNotIn("expected_answer", expectation_fields)
        self.assertNotIn("exact_answer", expectation_fields)
        self.assertIn("charging contacts", get_case("case_10").expectations.answer_requirements.must_mention)
        self.assertIn("can make coffee", get_case("case_14").expectations.answer_requirements.must_not_claim)

    def test_invalid_category_and_empty_turn_are_rejected(self):
        with self.assertRaises(ValueError):
            EvaluationCase(
                id="bad",
                name="Bad category",
                category="unknown",
                description="invalid",
                turns=(EvaluationTurn("hello"),),
                expectations=EvaluationExpectations(),
            )
        with self.assertRaises(ValueError):
            EvaluationTurn("")


if __name__ == "__main__":
    unittest.main()
