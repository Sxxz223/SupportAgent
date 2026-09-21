"""SQLite-backed case persistence tests."""
import main
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from my_project.api.session_store import SQLiteSessionStore


class SessionPersistenceTests(unittest.TestCase):
    def test_case_survives_new_store_instance(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "cases.db"
            first = SQLiteSessionStore(path)
            session_id = first.create_session()
            session = first.get_session(session_id)
            session.turn_index = 2
            session.case_version = 2
            session.state.product = "Anker Prime Charger"
            session.upsert_fact("current_port", "USB-C1", "user_confirmation", confirmed=True)
            session.service_tasks["charging"] = {
                "taskId": "charging", "name": "充电异常", "stage": "collecting",
                "statusText": "正在确认接口",
            }
            session.focus_task_id = "charging"
            session.history.append({"turn_index": 2, "role": "user", "content": "USB-C1"})
            first.save_session(session_id, session)

            restored = SQLiteSessionStore(path).get_session(session_id)
            self.assertEqual(restored.state.product, "Anker Prime Charger")
            self.assertEqual(restored.facts["current_port"].value, "USB-C1")
            self.assertEqual(restored.focus_task_id, "charging")
            self.assertEqual(restored.history[0]["content"], "USB-C1")


if __name__ == "__main__":
    unittest.main()
