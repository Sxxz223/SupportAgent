"""Program-owned multi-task lifecycle tests."""
import main
import unittest

from my_project.application.session import SupportSession
from my_project.workflow.task_engine import apply_task_updates, confirm_task_change, propose_task_change


def task(task_id, stage, status="状态"):
    return {"taskId": task_id, "name": task_id, "stage": stage, "statusText": status}


class TaskEngineTests(unittest.TestCase):
    def test_natural_confirmation_sentence_can_complete_but_negative_cannot(self):
        session = SupportSession(service_tasks={"charging": task("charging", "waiting_confirmation")})
        applied = apply_task_updates(session, [{
            "taskId": "charging", "name": "充电异常", "stage": "completed",
            "statusText": "已解决",
        }], "我确认这个问题已经解决了", False)
        self.assertEqual(applied[0]["stage"], "completed")

        session = SupportSession(service_tasks={"charging": task("charging", "waiting_confirmation")})
        applied = apply_task_updates(session, [{
            "taskId": "charging", "name": "充电异常", "stage": "completed",
            "statusText": "已解决",
        }], "这个问题还是没有解决", False)
        self.assertEqual(applied[0]["stage"], "waiting_confirmation")

    def test_unknown_task_is_blocked_without_confirmation(self):
        session = SupportSession(service_tasks={"a": task("a", "collecting")})
        applied = apply_task_updates(session, [task("b", "confirmed")], "继续", False)
        self.assertEqual(applied, [])
        self.assertNotIn("b", session.service_tasks)

    def test_completed_requires_explicit_customer_confirmation(self):
        session = SupportSession(service_tasks={"a": task("a", "solution_provided")})
        applied = apply_task_updates(session, [task("a", "completed")], "继续", False)
        self.assertEqual(applied[0]["stage"], "waiting_confirmation")
        applied = apply_task_updates(session, [task("a", "completed")], "task_complete:a", False)
        self.assertEqual(applied[0]["stage"], "completed")

    def test_waiting_confirmation_requires_a_real_solution(self):
        session = SupportSession(service_tasks={"a": task("a", "collecting")})
        applied = apply_task_updates(session, [task("a", "waiting_confirmation")], "继续", False)
        self.assertEqual(applied[0]["stage"], "collecting")

    def test_backward_transition_requires_reason(self):
        session = SupportSession(service_tasks={"a": task("a", "judgement_formed")})
        applied = apply_task_updates(session, [task("a", "collecting")], "继续", False)
        self.assertEqual(applied[0]["stage"], "judgement_formed")
        revised = {**task("a", "collecting"), "revisionReason": "新照片推翻了接口判断"}
        applied = apply_task_updates(session, [revised], "继续", False)
        self.assertEqual(applied[0]["stage"], "collecting")

    def test_cancel_change_needs_matching_confirmation(self):
        session = SupportSession(service_tasks={"a": task("a", "collecting")})
        change = {
            "changeId": "stop-a", "action": "cancel", "status": "proposed",
            "sourceTaskIds": ["a"], "candidateTasks": [], "reason": "用户不再需要",
        }
        propose_task_change(session, change)
        self.assertFalse(confirm_task_change(session, "继续"))
        self.assertEqual(session.service_tasks["a"]["stage"], "collecting")
        self.assertTrue(confirm_task_change(session, "task_change_confirm:stop-a"))
        self.assertEqual(session.service_tasks["a"]["stage"], "cancelled")


if __name__ == "__main__":
    unittest.main()
