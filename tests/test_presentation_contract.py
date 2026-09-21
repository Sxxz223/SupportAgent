"""Structured Agent response contract tests."""
import main
import unittest

from my_project.schemas.presentation import validate_presentation


class PresentationContractTests(unittest.TestCase):
    def test_only_one_proactive_message_can_enter_the_queue(self):
        result = validate_presentation({"proactiveMessages": [
            {"id": "first", "content": "一", "category": "supplement"},
            {"id": "second", "content": "二", "category": "supplement"},
        ]})
        self.assertEqual([item["id"] for item in result["proactiveMessages"]], ["first"])

    def test_valid_fields_are_normalized(self):
        result = validate_presentation({
            "taskDecision": {"type": "single"},
            "taskUpdates": [{
                "taskId": "charging", "name": "充电异常", "stage": "collecting",
                "statusText": "正在确认接口",
            }],
            "interaction": {"type": "choice", "options": [{"label": "USB-C 1"}]},
            "emotionState": {"state": "neutral", "trend": "stable"},
        })
        self.assertEqual(result["taskDecision"]["type"], "single")
        self.assertEqual(result["taskUpdates"][0]["stage"], "collecting")
        self.assertEqual(result["emotionState"]["state"], "neutral")

    def test_invalid_optional_field_is_dropped_without_losing_valid_fields(self):
        result = validate_presentation({
            "taskDecision": {"type": "invented"},
            "interaction": {"type": "choice", "options": [{"label": "继续"}]},
        })
        self.assertNotIn("taskDecision", result)
        self.assertEqual(result["interaction"]["type"], "choice")

    def test_invalid_plan_with_two_current_steps_is_rejected_by_turn_parser(self):
        from my_project.application.turn_processor import _parse_agent_output
        import json
        reply, view = _parse_agent_output(json.dumps({
            "reply": "继续排查。",
            "plan": {"steps": [
                {"id": "a", "title": "确认接口", "status": "current"},
                {"id": "b", "title": "测试线材", "status": "current"},
            ]},
        }))
        self.assertEqual(reply, "继续排查。")
        self.assertNotIn("plan", view)

    def test_unfinished_plan_requires_exactly_one_current_step(self):
        from my_project.application.turn_processor import _parse_agent_output
        import json
        _, view = _parse_agent_output(json.dumps({
            "reply": "继续。", "plan": {"steps": [
                {"id": "a", "title": "确认接口", "status": "pending"},
            ]},
        }))
        self.assertNotIn("plan", view)


if __name__ == "__main__":
    unittest.main()
