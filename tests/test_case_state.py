"""Unified case-state regression tests."""
import main  # Initialize the package alias used by the historical test suite.
import unittest

from my_project.application.session import SupportSession


class CaseStateTests(unittest.TestCase):
    def test_fact_replacement_keeps_source_and_revision_history(self):
        session = SupportSession(turn_index=1, case_version=0)
        session.upsert_fact("symptom", "no output", "user_text")
        session.turn_index = 2
        session.case_version = 1
        session.upsert_fact("symptom", "brief output then stops", "user_text")

        fact = session.facts["symptom"]
        self.assertEqual(fact.value, "brief output then stops")
        self.assertEqual(fact.turn_id, "turn_002")
        self.assertEqual(len(fact.history), 1)
        self.assertEqual(fact.history[0].value, "no output")

    def test_case_snapshot_round_trip_preserves_workspace(self):
        session = SupportSession(turn_index=3, case_version=2)
        session.upsert_fact("product", "A2345", "user_text")
        session.service_tasks["charging"] = {
            "taskId": "charging", "name": "充电异常", "stage": "collecting",
            "statusText": "正在确认接口",
        }
        session.focus_task_id = "charging"
        session.focus_path = {"currentState": "正在确认接口"}
        session.focus_plan = {"steps": [{"id": "port", "title": "确认当前接口", "status": "current"}]}
        session.presentation = {"interaction": {"type": "choice"}}

        snapshot = session.case_snapshot()
        restored = SupportSession()
        restored.restore_case(snapshot)

        self.assertEqual(restored.facts["product"].value, "A2345")
        self.assertEqual(restored.service_tasks, session.service_tasks)
        self.assertEqual(restored.focus_task_id, "charging")
        self.assertEqual(restored.focus_plan, session.focus_plan)
        self.assertEqual(restored.presentation["interaction"]["type"], "choice")

    def test_sensitive_conflict_waits_for_user_choice(self):
        session = SupportSession(turn_index=1)
        self.assertTrue(session.upsert_fact(
            "power_reading", "65W", "user_text", kind="observation",
            detect_conflict=True,
        ))
        session.turn_index = 2
        self.assertFalse(session.upsert_fact(
            "power_reading", "6.5W", "image_analysis", kind="observation",
            detect_conflict=True,
        ))
        self.assertEqual(session.facts["power_reading"].value, "65W")
        self.assertIn("power_reading", session.pending_fact_conflicts)

        resolved = session.resolve_fact_conflict("6.5W")
        self.assertEqual(resolved, ("power_reading", "6.5W"))
        self.assertEqual(session.facts["power_reading"].value, "6.5W")
        self.assertTrue(session.facts["power_reading"].confirmed)


if __name__ == "__main__":
    unittest.main()
