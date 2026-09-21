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


if __name__ == "__main__":
    unittest.main()
