"""Dynamic visual request and confirmation tests."""
import json
import main
import unittest
from types import SimpleNamespace

from my_project.application.session import SupportSession
from my_project.schemas.vision import VisionFieldUpdate
from my_project.vision.qwen import analyze_image_qwen


class FakeVisionClient:
    def __init__(self, payload):
        self.payload = payload
        self.prompt = ""
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.prompt = kwargs["messages"][0]["content"][1]["text"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.payload)))])


class DynamicVisionTests(unittest.TestCase):
    def test_partial_reshoot_reply_contains_only_the_current_visual_action(self):
        from my_project.application.turn_processor import _apply_vision_result_view
        session = SupportSession()
        session.pending_vision_fields = {
            "power_reading": {
                "key": "power_reading", "label": "当前功率", "value": None,
                "status": "unclear", "source": "image",
            }
        }
        session.pending_reshoot_target = "屏幕功率区域"
        view = {}
        reply = _apply_vision_result_view(session, view)
        self.assertEqual(view["interaction"]["type"], "partial_reshoot")
        self.assertEqual(reply, "这张照片有一部分没有看清，只需要补拍屏幕功率区域。")

    def test_visual_context_controls_requested_fields(self):
        client = FakeVisionClient({
            "fields": [
                {"key": "product_model", "label": "产品型号", "value": "A2345", "status": "recognized"},
                {"key": "power_reading", "label": "当前功率", "value": None, "status": "unclear"},
            ],
            "reshoot_target": "屏幕功率区域", "conflicts": [], "observation": "型号清楚，屏幕反光",
        })
        from pathlib import Path
        image = Path(__file__).resolve().parents[1] / "test_images" / "charging_contacts.png"
        update = analyze_image_qwen(
            str(image), client,
            visual_context={"target": "铭牌和屏幕", "fields": ["product_model", "power_reading"]},
            existing_facts={"power_reading": "65W"},
        )
        self.assertEqual([item.key for item in update.fields], ["product_model", "power_reading"])
        self.assertEqual(update.reshoot_target, "屏幕功率区域")
        self.assertIn('"extract_fields": ["product_model", "power_reading"]', client.prompt)

    def test_partial_reshoot_retains_recognized_fields(self):
        session = SupportSession(turn_index=1)
        session.stage_vision_result([
            VisionFieldUpdate(key="product_model", label="产品型号", value="A2345", status="recognized"),
            VisionFieldUpdate(key="power_reading", label="当前功率", value=None, status="unclear"),
        ], "屏幕区域")
        session.stage_vision_result([
            VisionFieldUpdate(key="power_reading", label="当前功率", value="65W", status="recognized"),
        ], None)
        self.assertEqual(session.pending_vision_fields["product_model"]["value"], "A2345")
        self.assertEqual(session.pending_vision_fields["power_reading"]["value"], "65W")

    def test_confirmed_visual_fields_enter_case(self):
        session = SupportSession(turn_index=1)
        session.stage_vision_result([
            VisionFieldUpdate(key="current_port", label="当前接口", value="USB-C1", status="recognized"),
        ], None)
        self.assertEqual(session.resolve_vision_confirmation("vision_confirm"), "confirmed")
        self.assertEqual(session.facts["current_port"].value, "USB-C1")
        self.assertTrue(session.facts["current_port"].confirmed)

    def test_visual_text_conflict_waits_for_clarification(self):
        session = SupportSession(turn_index=1)
        session.upsert_fact("power_reading", "65W", "user_text", kind="observation")
        session.stage_vision_result([
            VisionFieldUpdate(key="power_reading", label="当前功率", value="6.5W", status="recognized"),
        ], None)
        self.assertEqual(session.facts["power_reading"].value, "65W")
        self.assertEqual(session.pending_fact_conflicts["power_reading"]["incoming"], "6.5W")


if __name__ == "__main__":
    unittest.main()
