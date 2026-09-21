"""Detailed conversational fact extraction merge tests."""
import main
import unittest

from my_project.application.session import SupportSession
from my_project.application.turn_processor import _record_text_facts
from my_project.schemas.state import ExtractedFact, StateUpdate, SupportState
from my_project.workflow.stages import apply_update


class RichExtractionTests(unittest.TestCase):
    def test_detailed_facts_and_attempted_steps_enter_state_and_case(self):
        update = StateUpdate(
            issue="brief output then stops",
            facts={
                "target_device": ExtractedFact(value="电脑", kind="context"),
                "symptom": ExtractedFact(value="先跳一下然后没了", kind="observation"),
                "attempted_steps": ExtractedFact(value=["更换充电线"], kind="action"),
                "attempt_results": ExtractedFact(value="换线后仍无效", kind="result"),
            },
        )
        state = SupportState()
        session = SupportSession(state=state, turn_index=1)
        update = _record_text_facts(session, update)
        apply_update(state, update)

        self.assertEqual(state.diagnostic_facts["target_device"], "电脑")
        self.assertEqual(state.attempted_steps, ["更换充电线"])
        self.assertEqual(session.facts["symptom"].kind, "observation")
        self.assertEqual(session.facts["attempt_results"].value, "换线后仍无效")

    def test_customer_diagnosis_remains_a_judgement(self):
        update = StateUpdate(facts={
            "user_judgement": ExtractedFact(value="接口肯定坏了", kind="judgement"),
        })
        session = SupportSession(turn_index=1)
        _record_text_facts(session, update)
        self.assertEqual(session.facts["user_judgement"].kind, "judgement")
        self.assertFalse(session.facts["user_judgement"].confirmed)


if __name__ == "__main__":
    unittest.main()
