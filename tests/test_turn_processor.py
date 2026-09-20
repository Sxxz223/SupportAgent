"""Regression tests for session lifecycle and turn orchestration."""
import contextlib
import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import main as entry
from agents.tool_context import ToolContext
from application import turn_processor as processor
from application.context import AppContext
from application.session import SupportSession
from schemas.state import StateUpdate
from schemas.vision import VisionUpdate


class SessionTurnTests(unittest.TestCase):
    def test_identity_and_single_product_resolve_in_one_turn(self):
        session = SupportSession()
        session.state.user_name = "Alice"
        calls = []
        contexts = []

        def run(agent, _text, *, context):
            names = [tool.name for tool in agent.tools]
            calls.append(names)
            contexts.append(agent.instructions)
            if names == ["verify_customer"]:
                from tools.support_tools import verify_customer
                arguments = {"phone_last4": "3721"}
                tool_context = ToolContext(context=AppContext(session=context.session), tool_name=verify_customer.name, tool_call_id="verify", tool_arguments=json.dumps(arguments))
                asyncio.run(verify_customer.on_invoke_tool(tool_context, json.dumps(arguments)))
            elif names == ["get_owned_products"]:
                from tools.support_tools import get_owned_products
                arguments = {"customer_id": context.session.state.customer_id}
                tool_context = ToolContext(context=AppContext(session=context.session), tool_name=get_owned_products.name, tool_call_id="products", tool_arguments=json.dumps(arguments))
                asyncio.run(get_owned_products.on_invoke_tool(tool_context, json.dumps(arguments)))
            return SimpleNamespace(final_output="Please describe the issue with your product.")

        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=StateUpdate(phone_last4="3721")), \
             patch.object(processor.Runner, "run_sync", side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            answer = processor.process_turn(session, "3721")

        self.assertEqual(calls, [["verify_customer"], ["get_owned_products"], []])
        self.assertTrue(session.state.identity_verified)
        self.assertEqual(session.state.product_id, "anker-prime-250w")
        self.assertEqual(session.state.stage, "understand_issue")
        self.assertIn("ANK-DEMO-001", contexts[-1])
        self.assertEqual(answer, "Please describe the issue with your product.")

    def test_agent_step_limit_stops_a_state_changing_loop(self):
        session = SupportSession()
        calls = 0

        def run(_agent, _text, *, context):
            nonlocal calls
            calls += 1
            context.session.state.attempted_steps.append(str(calls))
            context.session.record_event("synthetic_tool")
            return SimpleNamespace(final_output="Stopped safely.")

        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=StateUpdate()), \
             patch.object(processor.Runner, "run_sync", side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            answer = processor.process_turn(session, "loop")

        self.assertEqual(calls, processor.MAX_AGENT_STEPS)
        self.assertEqual(answer, "Stopped safely.")
    def test_three_turns_share_state_and_build_history(self):
        session = SupportSession()
        state_identity = id(session.state)
        updates = iter([
            StateUpdate(user_name="Alice"),
            StateUpdate(phone_last4="3721"),
            StateUpdate(product="Anker Prime Charger (250W, 6 Ports, GaNPrime)"),
            StateUpdate(issue="It doesn't seem to be receiving power."),
        ])
        stages = []
        agents = []

        def run(agent, text, **kwargs):
            agents.append(agent)
            self.assertIs(kwargs["context"].session, session)
            if len(agents) == 2:
                session.state.customer_id = "00000000-0000-0000-0000-000000000001"
                session.state.identity_verified = True
            return SimpleNamespace(final_output=f"response-{len(agents)}")

        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", side_effect=lambda *_: next(updates)), \
             patch.object(processor, "create_embedding_model", return_value="embedding") as embedding, \
             patch.object(processor, "search_knowledge", return_value="CHARGING KNOWLEDGE") as search, \
             patch.object(processor.Runner, "run_sync", side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            processor.process_turn(session, "I'm Alice.")
            stages.append(session.state.stage)
            self.assertEqual(id(session.state), state_identity)
            processor.process_turn(session, "3721")
            stages.append(session.state.stage)
            processor.process_turn(session, "My product is Anker Prime Charger (250W, 6 Ports, GaNPrime).")
            stages.append(session.state.stage)
            self.assertEqual(id(session.state), state_identity)
            processor.process_turn(session, "It doesn't seem to be receiving power.")
            stages.append(session.state.stage)

        self.assertEqual(stages, ["verify_identity", "identify_product", "understand_issue", "diagnose"])
        self.assertEqual(session.state.user_name, "Alice")
        self.assertEqual(session.state.product, "Anker Prime Charger (250W, 6 Ports, GaNPrime)")
        self.assertEqual(session.state.issue, "It doesn't seem to be receiving power.")
        self.assertEqual(session.turn_index, 4)
        self.assertEqual(len(session.history), 8)
        self.assertEqual(
            [(item["turn_index"], item["role"]) for item in session.history],
            [(1, "user"), (1, "assistant"), (2, "user"),
             (2, "assistant"), (3, "user"), (3, "assistant"),
             (4, "user"), (4, "assistant")],
        )
        self.assertEqual(session.history[0]["content"], "I'm Alice.")
        self.assertEqual(session.history[-1]["content"], "response-4")
        embedding.assert_called_once_with()
        search.assert_called_once_with(
            "Anker Prime Charger (250W, 6 Ports, GaNPrime) It doesn't seem to be receiving power.",
            "embedding",
            product="Anker Prime Charger (250W, 6 Ports, GaNPrime)",
            product_id="anker-prime-250w",
        )
        self.assertEqual([tool.name for tool in agents[0].tools], ["verify_customer"])
        self.assertEqual([tool.name for tool in agents[1].tools], ["verify_customer"])
        self.assertEqual([tool.name for tool in agents[2].tools], [])
        self.assertEqual(
            [tool.name for tool in agents[3].tools],
            ["check_warranty", "create_ticket"],
        )
        self.assertIn("CHARGING KNOWLEDGE", agents[3].instructions)
        self.assertEqual(
            [event.event_type for event in session.events],
            ["rag_retrieved"],
        )

    def test_vision_is_current_only_for_image_turn(self):
        session = SupportSession()
        session.state.customer_id = "customer-1"
        session.state.identity_verified = True
        agents = []
        updates = iter([
            StateUpdate(user_name="Alice", product="Anker Prime Charger (250W, 6 Ports, GaNPrime)", issue="won't charge"),
            StateUpdate(),
        ])
        image = str(Path(entry.__file__).parent / "test_images/charging_contacts.png")

        def run(agent, _, **kwargs):
            agents.append(agent)
            self.assertIs(kwargs["context"].session, session)
            return SimpleNamespace(final_output="response")

        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", side_effect=lambda *_: next(updates)), \
             patch.object(processor, "create_qwen_client", return_value="qwen") as qwen, \
             patch.object(processor, "analyze_image_qwen", return_value=VisionUpdate(
                 dock_visible=True,
                 indicator_on=True,
                 contacts_dirty=True,
                 robot_on_dock=True,
                 observation="Dirty contacts are visible.",
             )) as analyze, \
             patch.object(processor, "create_embedding_model", return_value="embedding"), \
             patch.object(processor, "search_knowledge", return_value="knowledge"), \
             patch.object(processor.Runner, "run_sync", side_effect=run), \
             contextlib.redirect_stdout(io.StringIO()):
            processor.process_turn(session, "Here is a photo.", image)
            processor.process_turn(session, "What should I do now?")

        self.assertTrue(session.state.image_received)
        self.assertTrue(session.state.contacts_dirty)
        self.assertEqual(
            [event.event_type for event in session.events].count("vision_analyzed"),
            1,
        )
        self.assertIn("source: image analyzed in the current turn", agents[0].instructions)
        self.assertIn("Dirty contacts are visible.", agents[0].instructions)
        self.assertIn("no image was provided or analyzed in the current turn", agents[1].instructions)
        self.assertIn("source: historical image observation from turn 1", agents[1].instructions)
        self.assertIn(
            "this was not observed in the current turn",
            agents[1].instructions,
        )
        self.assertIn("Dirty contacts are visible.", agents[1].instructions)
        qwen.assert_called_once_with()
        analyze.assert_called_once_with(image, "qwen")

    def test_all_updates_precede_decisions(self):
        session = SupportSession()
        session.state.customer_id = "customer-1"
        session.state.identity_verified = True
        events = []
        snapshots = {}
        originals = {
            name: getattr(processor, name)
            for name in (
                "apply_update", "apply_vision_update", "next_stage",
                "decide_next_action", "get_allowed_tools",
            )
        }

        def observe(name):
            def call(*args, **kwargs):
                events.append(name)
                snapshots[name] = vars(session.state).copy()
                return originals[name](*args, **kwargs)
            return call

        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(patch.object(processor, "create_deepseek_model", return_value="model"))
            stack.enter_context(patch.object(processor, "extract_state_update", return_value=StateUpdate(
                user_name="Alice", product="Anker Prime Charger (250W, 6 Ports, GaNPrime)", issue="won't charge"
            )))
            stack.enter_context(patch.object(processor, "create_qwen_client", return_value="qwen"))
            stack.enter_context(patch.object(processor, "analyze_image_qwen", side_effect=lambda *_: (
                events.append("vision") or VisionUpdate(indicator_on=True, contacts_dirty=True)
            )))
            stack.enter_context(patch.object(processor, "create_embedding_model", return_value="embedding"))
            stack.enter_context(patch.object(processor, "search_knowledge", side_effect=lambda *_, **__: (
                events.append("retrieval") or "knowledge"
            )))
            stack.enter_context(patch.object(
                processor.Runner, "run_sync", return_value=SimpleNamespace(final_output="response")
            ))
            for name in originals:
                stack.enter_context(patch.object(processor, name, side_effect=observe(name)))
            processor.process_turn(session, "input", "image.png")

        self.assertEqual(events, [
            "apply_update", "vision", "apply_vision_update", "next_stage",
            "retrieval", "decide_next_action", "get_allowed_tools", "next_stage",
            "decide_next_action", "get_allowed_tools",
        ])
        for name in ("next_stage", "decide_next_action"):
            self.assertEqual(snapshots[name]["issue"], "won't charge")
            self.assertTrue(snapshots[name]["image_received"])
            self.assertTrue(snapshots[name]["contacts_dirty"])

    def test_no_image_does_not_create_qwen_client(self):
        session = SupportSession()
        with patch.object(processor, "create_deepseek_model", return_value="model"), \
             patch.object(processor, "extract_state_update", return_value=StateUpdate(user_name="Alice")), \
             patch.object(processor, "create_qwen_client") as qwen, \
             patch.object(processor, "analyze_image_qwen") as analyze, \
             patch.object(processor.Runner, "run_sync", return_value=SimpleNamespace(final_output="response")), \
             contextlib.redirect_stdout(io.StringIO()):
            processor.process_turn(session, "I'm Alice.")
        qwen.assert_not_called()
        analyze.assert_not_called()

    def test_main_reuses_one_session_until_exit(self):
        seen_sessions = []

        def process(session, text, image):
            seen_sessions.append(session)
            return f"response to {text}"

        with patch.object(entry, "process_turn", side_effect=process), \
             patch("builtins.input", side_effect=["first", "", "second", "photo.png", "exit"]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            entry.main()

        self.assertEqual(len(seen_sessions), 2)
        self.assertIs(seen_sessions[0], seen_sessions[1])
        self.assertIn("response to first", output.getvalue())
        self.assertIn("response to second", output.getvalue())


class ResourceLifecycleTests(unittest.TestCase):
    def test_provider_and_embedding_factories_are_singletons(self):
        from providers import deepseek, qwen
        from rag import embeddings

        deepseek.create_deepseek_model.cache_clear()
        qwen.create_qwen_client.cache_clear()
        embeddings.create_embedding_model.cache_clear()
        self.addCleanup(deepseek.create_deepseek_model.cache_clear)
        self.addCleanup(qwen.create_qwen_client.cache_clear)
        self.addCleanup(embeddings.create_embedding_model.cache_clear)

        deepseek_model = object()
        qwen_client = object()
        embedding_model = object()
        with patch.dict("os.environ", {
                 "DEEPSEEK_API_KEY": "test-key",
                 "DASHSCOPE_API_KEY": "test-key",
             }), \
             patch.object(deepseek, "AsyncOpenAI") as deepseek_ctor, \
             patch.object(deepseek, "OpenAIChatCompletionsModel", return_value=deepseek_model) as model_ctor, \
             patch.object(qwen, "OpenAI", return_value=qwen_client) as qwen_ctor, \
             patch.object(embeddings, "SentenceTransformer", return_value=embedding_model) as embedding_ctor:
            self.assertIs(deepseek.create_deepseek_model(), deepseek_model)
            self.assertIs(deepseek.create_deepseek_model(), deepseek_model)
            self.assertIs(qwen.create_qwen_client(), qwen_client)
            self.assertIs(qwen.create_qwen_client(), qwen_client)
            self.assertIs(embeddings.create_embedding_model(), embedding_model)
            self.assertIs(embeddings.create_embedding_model(), embedding_model)

        deepseek_ctor.assert_called_once()
        model_ctor.assert_called_once()
        qwen_ctor.assert_called_once()
        embedding_ctor.assert_called_once_with("sentence-transformers/all-MiniLM-L6-v2")


if __name__ == "__main__":
    unittest.main()
