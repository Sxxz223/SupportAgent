"""Proactive event scheduling and invalidation tests."""
import main
import time
import unittest
from unittest.mock import patch

from my_project.application.session import SupportSession
from my_project.application.turn_processor import process_turn


class ProactiveEventTests(unittest.TestCase):
    @patch("my_project.application.turn_processor.create_deepseek_model", return_value="model")
    @patch("my_project.application.turn_processor.extract_state_update")
    @patch("my_project.application.turn_processor.Runner.run_sync")
    def test_waiting_turn_queues_a_later_question_and_action_update(self, run, extract, _model):
        from my_project.schemas.state import StateUpdate
        from types import SimpleNamespace
        import json

        extract.return_value = StateUpdate()
        run.return_value = SimpleNamespace(final_output=json.dumps({
            "reply": "好的，我等你。", "taskDecision": {"type": "single"},
            "taskUpdates": [], "interaction": {"type": "none"},
            "emotionState": {"state": "neutral", "trend": "stable"},
            "agentState": {"emoji": "🤗", "label": "耐心等你"},
        }, ensure_ascii=False))
        session = SupportSession(
            focus_task_id="charging",
            service_tasks={"charging": {
                "taskId": "charging", "name": "充电异常", "stage": "collecting",
                "statusText": "等待换线结果",
            }},
        )

        process_turn(session, "我现在去换线，稍等一下")

        self.assertEqual(
            [event["eventType"] for event in session.proactive_events],
            ["agent_state", "proactive_message", "interaction_update"],
        )
        self.assertIn("？", session.proactive_events[1]["content"])
        self.assertEqual(session.proactive_events[2]["interaction"]["type"], "choice")

    @patch("my_project.application.turn_processor.create_deepseek_model", return_value="model")
    @patch("my_project.application.turn_processor.extract_state_update")
    @patch("my_project.application.turn_processor.Runner.run_sync")
    def test_output_queues_timed_versioned_events(self, run, extract, _model):
        from my_project.schemas.state import StateUpdate
        from types import SimpleNamespace
        import json

        extract.return_value = StateUpdate()
        run.return_value = SimpleNamespace(final_output=json.dumps({
            "reply": "请先试一下。",
            "agentState": {"emoji": "🤝", "label": "陪着你"},
            "emotionState": {"state": "anxious", "trend": "stable"},
            "proactiveMessages": [{
                "id": "pm-1", "content": "刚才的信息已经保留。",
                "category": "reassurance", "delaySeconds": 2,
                "expiresInSeconds": 10,
            }],
        }, ensure_ascii=False))
        session = SupportSession()

        process_turn(session, "我有点着急")

        self.assertEqual(
            [item["eventType"] for item in session.proactive_events],
            ["agent_state", "proactive_message"],
        )
        self.assertEqual(session.proactive_events[0]["emoji"], "🤝")
        self.assertEqual(session.proactive_events[0]["label"], "陪着你")
        message = session.proactive_events[1]
        self.assertEqual(message["turnId"], "turn_001")
        self.assertEqual(message["caseVersion"], 1)
        self.assertGreater(message["deliverAt"], time.time())
        self.assertGreater(message["expiresAt"], message["deliverAt"])

    def test_new_turn_clears_stale_events_before_model_work(self):
        session = SupportSession()
        session.proactive_events.append({"eventType": "proactive_message", "id": "old"})
        with patch("my_project.application.turn_processor.create_deepseek_model", side_effect=RuntimeError("stop")):
            with self.assertRaises(RuntimeError):
                process_turn(session, "新的输入")
        self.assertNotIn("old", [item.get("id") for item in session.proactive_events])
        self.assertEqual(session.proactive_events, [])


if __name__ == "__main__":
    unittest.main()
