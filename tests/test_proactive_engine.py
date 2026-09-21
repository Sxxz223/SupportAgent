"""Waiting-state and proactive-message decision tests."""
import main
import unittest

from my_project.application.session import SupportSession
from my_project.workflow.proactive_engine import apply_waiting_and_proactive_state


class ProactiveEngineTests(unittest.TestCase):
    def test_explicit_wait_with_active_task_gets_one_bounded_message(self):
        session = SupportSession(focus_task_id="charging", turn_index=3)
        view = {"emotionState": {"state": "frustrated", "trend": "stable"}}
        apply_waiting_and_proactive_state(session, view, "我现在去换线，稍等一下")
        self.assertEqual(session.interaction_state["status"], "waiting_for_user_action")
        self.assertEqual(len(view["proactiveMessages"]), 1)
        self.assertEqual(view["proactiveMessages"][0]["delaySeconds"], 2)
        self.assertEqual(view["proactiveMessages"][0]["category"], "followup")
        self.assertEqual(view["proactiveMessages"][0]["interaction"]["type"], "choice")

    def test_no_active_task_or_no_wait_stays_quiet(self):
        no_task = SupportSession(turn_index=1)
        view = {}
        apply_waiting_and_proactive_state(no_task, view, "我去试一下")
        self.assertNotIn("proactiveMessages", view)

        active = SupportSession(focus_task_id="charging", turn_index=2)
        view = {}
        apply_waiting_and_proactive_state(active, view, "这是测试结果")
        self.assertEqual(active.interaction_state["status"], "ready")
        self.assertNotIn("proactiveMessages", view)

    def test_model_message_is_preserved_instead_of_duplicated(self):
        session = SupportSession(focus_task_id="charging", turn_index=2)
        original = [{"id": "model-message", "content": "已有补充"}]
        view = {"proactiveMessages": original}
        apply_waiting_and_proactive_state(session, view, "稍等一下")
        self.assertIs(view["proactiveMessages"], original)


if __name__ == "__main__":
    unittest.main()
