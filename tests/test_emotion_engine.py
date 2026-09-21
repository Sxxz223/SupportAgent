"""Communication emotion state must stay independent from business decisions."""
import main
import unittest

from my_project.application.session import SupportSession
from my_project.workflow.emotion_engine import apply_emotion_state


class EmotionEngineTests(unittest.TestCase):
    def test_emotion_trend_is_derived_across_turns(self):
        session = SupportSession()
        session.turn_index = 1
        view = {"emotionState": {"state": "frustrated", "trend": "stable"}}
        apply_emotion_state(session, view, "怎么还不行")
        self.assertEqual(view["emotionState"], {"state": "frustrated", "trend": "worsening"})

        session.turn_index = 2
        view = {"emotionState": {"state": "calm", "trend": "stable"}}
        apply_emotion_state(session, view, "明白了，谢谢")
        self.assertEqual(view["emotionState"]["trend"], "improving")

    def test_fallback_detects_clear_signal_without_changing_business_state(self):
        session = SupportSession()
        session.state.product = "Anker Prime Charger"
        session.service_tasks["charging"] = {"taskId": "charging", "stage": "collecting"}
        before_state = session.state
        before_tasks = dict(session.service_tasks)

        view = {}
        result = apply_emotion_state(session, view, "我明天急用，真的很担心")

        self.assertEqual(result["state"], "anxious")
        self.assertIs(session.state, before_state)
        self.assertEqual(session.service_tasks, before_tasks)

    def test_emotion_history_is_bounded(self):
        session = SupportSession()
        for turn in range(30):
            session.turn_index = turn
            apply_emotion_state(session, {}, "继续")
        self.assertEqual(len(session.emotion_history), 20)


if __name__ == "__main__":
    unittest.main()
