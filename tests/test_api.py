"""HTTP API regression tests with the Agent boundary replaced by a deterministic fake."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID

import main  # Initialize project/SDK import separation.
from fastapi.testclient import TestClient

from my_project.api.app import create_app
from my_project.api.session_store import InMemorySessionStore
from my_project.application import turn_processor
from my_project.schemas.state import StateUpdate
from my_project.schemas.vision import VisionUpdate
from my_project.workflow.stages import next_stage


class FakeTurnProcessor:
    def __init__(self) -> None:
        self.calls = []
        self.uploads = []

    def __call__(self, *, session, user_input, image_path=None):
        self.calls.append((session, user_input, image_path))
        if image_path is not None:
            path = Path(image_path)
            self.uploads.append((image_path, path.read_bytes()))
            session.state.image_received = True
        text = user_input.lower()
        if "alice" in text:
            session.state.user_name = "Alice"
        if "bob" in text:
            session.state.user_name = "Bob"
        if "prime charger" in text:
            session.state.product = "Anker Prime Charger (250W, 6 Ports, GaNPrime)"
            session.state.product_id = "anker-prime-250w"
        session.state.stage = next_stage(session.state)
        session.turn_index += 1
        session.history.extend([
            {"turn_index": session.turn_index, "role": "user", "content": user_input},
            {"turn_index": session.turn_index, "role": "assistant", "content": f"reply: {user_input}"},
        ])
        return f"reply: {user_input}"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemorySessionStore()
        self.processor = FakeTurnProcessor()
        self.client = TestClient(create_app(self.store, self.processor))

    def create_session(self):
        response = self.client.post("/session")
        self.assertEqual(response.status_code, 200)
        return response.json()["session_id"]

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_create_session_returns_uuid_and_stores_session(self):
        session_id = self.create_session()
        self.assertEqual(str(UUID(session_id)), session_id)
        self.assertIsNotNone(self.store.get_session(session_id))

    def test_typing_activity_cancels_the_scheduled_introduction(self):
        session_id = self.create_session()
        session = self.store.get_session(session_id)
        self.assertTrue(session.proactive_events)
        response = self.client.post(
            f"/session/{session_id}/activity", json={"activity": "typing"}
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(session.proactive_events, [])

    def test_idle_activity_uses_persona_decider_after_conversation(self):
        decisions = []

        def decide(session, activity):
            decisions.append((session, activity))
            return {"action": "small_talk", "content": "我还在这儿，慢慢来。",
                    "emoji": "🌿", "label": "轻松陪着你"}

        store = InMemorySessionStore()
        client = TestClient(create_app(store, FakeTurnProcessor(), behavior_decider=decide))
        session_id = client.post("/session").json()["session_id"]
        client.post("/chat", json={"session_id": session_id, "message": "hello"})
        response = client.post(
            f"/session/{session_id}/activity", json={"activity": "idle"}
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(decisions[0][1], "idle")
        session = store.get_session(session_id)
        self.assertEqual(session.proactive_events[1]["category"], "small_talk")
        self.assertEqual(session.proactive_events[1]["content"], "我还在这儿，慢慢来。")

    def test_chat_calls_process_turn_with_matching_session(self):
        session_id = self.create_session()
        session = self.store.get_session(session_id)

        response = self.client.post("/chat", json={
            "session_id": session_id,
            "message": "I'm Alice.",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "reply": "reply: I'm Alice.",
            "stage": "verify_identity",
        })
        self.assertIs(self.processor.calls[0][0], session)
        self.assertEqual(self.processor.calls[0][1:], ("I'm Alice.", None))

    def test_second_chat_reuses_first_turn_state(self):
        session_id = self.create_session()
        first_session = self.store.get_session(session_id)
        self.client.post("/chat", json={
            "session_id": session_id,
            "message": "I'm Alice.",
        })

        response = self.client.post("/chat", json={
            "session_id": session_id,
            "message": "My product is Anker Prime Charger (250W, 6 Ports, GaNPrime).",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stage"], "verify_identity")
        self.assertIs(self.processor.calls[1][0], first_session)
        self.assertEqual(first_session.state.user_name, "Alice")
        self.assertEqual(first_session.state.product, "Anker Prime Charger (250W, 6 Ports, GaNPrime)")
        self.assertEqual(first_session.turn_index, 2)

    def test_unknown_session_returns_404_without_creating_one(self):
        missing_id = str(UUID("00000000-0000-0000-0000-000000000001"))

        response = self.client.post("/chat", json={
            "session_id": missing_id,
            "message": "Hello",
        })

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Support session not found"})
        self.assertIsNone(self.store.get_session(missing_id))
        self.assertEqual(self.processor.calls, [])

    def test_multiple_session_ids_do_not_share_state(self):
        alice_id = self.create_session()
        bob_id = self.create_session()
        self.client.post("/chat", json={"session_id": alice_id, "message": "I'm Alice."})
        self.client.post("/chat", json={"session_id": bob_id, "message": "I'm Bob."})
        self.client.post("/chat", json={
            "session_id": alice_id,
            "message": "My product is Anker Prime Charger (250W, 6 Ports, GaNPrime).",
        })

        alice = self.store.get_session(alice_id)
        bob = self.store.get_session(bob_id)
        self.assertIsNot(alice, bob)
        self.assertIsNot(alice.state, bob.state)
        self.assertEqual(alice.state.user_name, "Alice")
        self.assertEqual(alice.state.product, "Anker Prime Charger (250W, 6 Ports, GaNPrime)")
        self.assertEqual(bob.state.user_name, "Bob")
        self.assertIsNone(bob.state.product)

    def test_cors_allows_only_configured_local_frontend(self):
        response = self.client.options("/chat", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:5173",
        )

    def test_multimodal_upload_uses_temp_path_and_cleans_it(self):
        session_id = self.create_session()
        image_bytes = (Path(__file__).parents[1] / "test_images" / "charging_contacts.png").read_bytes()

        response = self.client.post(
            "/chat/multimodal",
            data={
                "session_id": session_id,
                "message": "Can you check this photo?",
            },
            files={"image": ("charging.png", image_bytes, "image/png")},
        )

        self.assertEqual(response.status_code, 200)
        session, message, image_path = self.processor.calls[-1]
        self.assertIs(session, self.store.get_session(session_id))
        self.assertEqual(message, "Can you check this photo?")
        self.assertEqual(self.processor.uploads[-1][1], image_bytes)
        self.assertFalse(Path(image_path).exists())
        self.assertTrue(session.state.image_received)

    def test_multimodal_allows_image_without_message(self):
        session_id = self.create_session()
        image_bytes = (Path(__file__).parents[1] / "test_images" / "charging_contacts.png").read_bytes()

        response = self.client.post(
            "/chat/multimodal",
            data={"session_id": session_id, "message": ""},
            files={"image": ("charging.png", image_bytes, "image/png")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.processor.calls[-1][1], "")

    def test_multimodal_rejects_non_image_file(self):
        session_id = self.create_session()
        response = self.client.post(
            "/chat/multimodal",
            data={"session_id": session_id, "message": "look"},
            files={"image": ("notes.txt", b"not an image", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported image type", response.json()["detail"])
        self.assertEqual(self.processor.calls, [])

    def test_multimodal_rejects_file_over_ten_megabytes(self):
        session_id = self.create_session()
        oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (10 * 1024 * 1024)

        response = self.client.post(
            "/chat/multimodal",
            data={"session_id": session_id, "message": "look"},
            files={"image": ("large.png", oversized, "image/png")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("10 MB", response.json()["detail"])
        self.assertEqual(self.processor.calls, [])

    def test_multimodal_then_text_reuses_the_same_session(self):
        session_id = self.create_session()
        image_bytes = (Path(__file__).parents[1] / "test_images" / "charging_contacts.png").read_bytes()
        self.client.post(
            "/chat/multimodal",
            data={"session_id": session_id, "message": "photo"},
            files={"image": ("charging.png", image_bytes, "image/png")},
        )

        response = self.client.post("/chat", json={
            "session_id": session_id,
            "message": "I'm Alice.",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIs(self.processor.calls[-2][0], self.processor.calls[-1][0])
        self.assertTrue(self.processor.calls[-1][0].state.image_received)


class EvaluationDebugApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.report_path = Path(self.temporary_directory.name) / "evaluation_results.json"
        self.report = {
            "total": 16,
            "passed": 13,
            "failed": 2,
            "known_limitations": 1,
            "errors": 0,
            "case_results": [{"case_id": "case_01", "status": "PASS"}],
            "duration_ms": 123.45,
        }
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        self.client = TestClient(create_app(
            InMemorySessionStore(),
            FakeTurnProcessor(),
            evaluation_report_path=self.report_path,
        ))

    def test_latest_returns_complete_existing_report(self):
        response = self.client.get("/debug/evaluation/latest")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.report)

    def test_summary_uses_values_from_complete_report(self):
        response = self.client.get("/debug/evaluation/summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            key: self.report[key]
            for key in (
                "total", "passed", "failed", "known_limitations", "errors", "duration_ms"
            )
        })

    def test_missing_report_returns_clear_404_without_running_evaluation(self):
        self.report_path.unlink()

        response = self.client.get("/debug/evaluation/latest")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {
            "detail": "No evaluation report found. Run the evaluation CLI first."
        })

    def test_invalid_json_returns_safe_error_without_traceback(self):
        self.report_path.write_text("{not valid json", encoding="utf-8")

        response = self.client.get("/debug/evaluation/latest")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {
            "detail": "Evaluation report is invalid or unreadable."
        })
        self.assertNotIn("Traceback", response.text)

    def test_summary_rejects_report_without_existing_aggregate_fields(self):
        self.report_path.write_text(json.dumps({"case_results": []}), encoding="utf-8")

        response = self.client.get("/debug/evaluation/summary")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {
            "detail": "Evaluation report is invalid or unreadable."
        })

    def test_openapi_lists_read_only_evaluation_endpoints_under_evaluation_tag(self):
        schema = self.client.get("/openapi.json").json()

        self.assertEqual(
            schema["paths"]["/debug/evaluation/latest"]["get"]["tags"],
            ["Evaluation"],
        )
        self.assertEqual(
            schema["paths"]["/debug/evaluation/summary"]["get"]["tags"],
            ["Evaluation"],
        )
        self.assertNotIn("post", schema["paths"]["/debug/evaluation/latest"])


class MultimodalCoreIntegrationTests(unittest.TestCase):
    def test_upload_enters_existing_vision_and_agent_context(self):
        store = InMemorySessionStore()
        session_id = store.create_session()
        verified_session = store.get_session(session_id)
        verified_session.state.customer_id = "00000000-0000-0000-0000-000000000001"
        verified_session.state.identity_verified = True
        client = TestClient(create_app(store))
        image_bytes = (Path(__file__).parents[1] / "test_images" / "charging_contacts.png").read_bytes()

        with patch.object(turn_processor, "create_deepseek_model", return_value="model"), \
             patch.object(turn_processor, "extract_state_update", return_value=StateUpdate(
                 user_name="Alice", product="Anker Prime Charger (250W, 6 Ports, GaNPrime)", issue="won't charge"
             )), \
             patch.object(turn_processor, "create_qwen_client", return_value="qwen"), \
             patch.object(turn_processor, "analyze_image_qwen", return_value=VisionUpdate(
                 indicator_on=True,
                 contacts_dirty=True,
                 observation="Dirty contacts are visible.",
             )) as analyze, \
             patch.object(turn_processor, "create_embedding_model", return_value="embedding"), \
             patch.object(turn_processor, "search_knowledge", return_value="charging knowledge"), \
             patch.object(turn_processor.Runner, "run_sync", return_value=SimpleNamespace(
                 final_output="Clean the charging contacts."
             )) as runner:
            response = client.post(
                "/chat/multimodal",
                data={
                    "session_id": session_id,
                    "message": "My Anker Prime Charger (250W, 6 Ports, GaNPrime) won't charge. Can you check this photo?",
                },
                files={"image": ("charging.png", image_bytes, "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "Clean the charging contacts.")
        session = store.get_session(session_id)
        self.assertTrue(session.state.image_received)
        self.assertTrue(session.state.contacts_dirty)
        self.assertEqual(session.state.stage, "diagnose")
        analyzed_path = Path(analyze.call_args.args[0])
        self.assertFalse(analyzed_path.exists())
        agent = runner.call_args.args[0]
        self.assertIn("image analyzed in the current turn", agent.instructions)
        self.assertIn("contacts_dirty: True", agent.instructions)
        self.assertIn("clean_charging_contacts", agent.instructions)


if __name__ == "__main__":
    unittest.main()
