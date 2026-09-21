"""Focused-task and live-path rule tests."""
import main
import unittest

from my_project.application.session import SupportSession
from my_project.workflow.focus_engine import apply_focus_change, apply_live_plan


def task(task_id, stage):
    return {"taskId": task_id, "name": task_id, "stage": stage, "statusText": "状态"}


class FocusEngineTests(unittest.TestCase):
    def test_focus_does_not_jump_without_a_valid_reason(self):
        session = SupportSession(
            service_tasks={"a": task("a", "collecting"), "b": task("b", "collecting")},
            focus_task_id="a", focus_path={"currentState": "处理A"},
            focus_plan={"steps": [{"id": "a1", "title": "确认A", "status": "current"}]},
        )
        view = {"focusTaskId": "b", "focusChanged": True, "focusChangeReason": "顺便处理B"}
        apply_focus_change(session, view, "继续", "接下来处理B")
        self.assertEqual(view["focusTaskId"], "a")
        self.assertFalse(view["focusChanged"])

    def test_waiting_task_can_switch_when_reply_explains_reason(self):
        session = SupportSession(
            service_tasks={"a": task("a", "waiting_confirmation"), "b": task("b", "confirmed")},
            focus_task_id="a",
        )
        reason = "任务A正在等待实际测试"
        view = {"focusTaskId": "b", "focusChanged": True, "focusChangeReason": reason}
        apply_focus_change(session, view, "继续", f"{reason}，现在处理B。")
        self.assertEqual(session.focus_task_id, "b")
        self.assertEqual(len(session.focus_history), 1)

    def test_plan_change_gets_revision_note_and_history(self):
        session = SupportSession(
            focus_task_id="a",
            focus_plan={"steps": [
                {"id": "cable", "title": "测试线材", "status": "current"},
                {"id": "verify", "title": "验证状态", "status": "pending"},
            ]},
        )
        view = {"plan": {"steps": [
            {"id": "cable", "title": "测试线材", "status": "done"},
            {"id": "port", "title": "测试其他接口", "status": "current"},
            {"id": "verify", "title": "验证状态", "status": "pending"},
        ]}}
        apply_live_plan(session, view)
        self.assertIn("增加", view["plan"]["revision_note"])
        self.assertEqual(session.path_history[0]["added"], ["port"])


if __name__ == "__main__":
    unittest.main()
