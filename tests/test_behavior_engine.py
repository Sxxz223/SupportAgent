"""Persistent observation and personified behavior tests."""
import main
import unittest

from my_project.application.session import SupportSession
from my_project.workflow.behavior_engine import apply_behavior_decision, event_is_current, observe_activity


class BehaviorEngineTests(unittest.TestCase):
    def test_new_session_schedules_one_delayed_introduction(self):
        session = SupportSession()
        observe_activity(session, "session_created")
        self.assertTrue(session.behavior_state["introductionScheduled"])
        self.assertEqual(
            [item["eventType"] for item in session.proactive_events],
            ["agent_state", "proactive_message"],
        )
        self.assertIn("可以直接描述", session.proactive_events[1]["content"])

        observe_activity(session, "session_created")
        self.assertEqual(session.proactive_events, [])

    def test_typing_cancels_the_pending_introduction(self):
        session = SupportSession()
        observe_activity(session, "session_created")
        old = dict(session.proactive_events[1])
        observe_activity(session, "typing")
        self.assertEqual(session.proactive_events, [])
        self.assertFalse(event_is_current(session, old))

    def test_image_selection_gets_contextual_acknowledgement(self):
        session = SupportSession()
        observe_activity(session, "image_selected")
        message = session.proactive_events[1]
        self.assertEqual(message["category"], "acknowledgement")
        self.assertIn("图片", message["content"])

    def test_behavior_state_survives_case_restore(self):
        session = SupportSession()
        observe_activity(session, "session_created")
        restored = SupportSession()
        restored.restore_case(session.case_snapshot())
        self.assertTrue(restored.behavior_state["introductionScheduled"])
        self.assertEqual(restored.behavior_state["activityVersion"], 1)

    def test_model_decision_can_speak_or_stay_silent_without_business_mutation(self):
        session = SupportSession()
        apply_behavior_decision(session, {
            "action": "encourage", "content": "慢慢来，我在这里。",
            "emoji": "🌿", "label": "安静陪着你",
        })
        self.assertEqual(session.proactive_events[1]["content"], "慢慢来，我在这里。")
        before = len(session.proactive_events)
        apply_behavior_decision(session, {"action": "stay_silent"})
        self.assertEqual(len(session.proactive_events), before)
        self.assertEqual(session.service_tasks, {})


if __name__ == "__main__":
    unittest.main()
