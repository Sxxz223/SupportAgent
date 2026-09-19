"""Offline regression checks. Run: .venv/bin/python -m unittest discover -s tests -v."""
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import main as entry  # Entry bootstrap separates local agents from the SDK.
from my_project.application import turn_processor
from my_project.application.session import SupportSession
from my_project.application.session import TurnContext
from my_project.context.builder import build_model_context
from agents import Agent
from my_project.agents.extractor_agent import create_extractor_agent, extract_state_update
from my_project.agents.support_agent import create_support_agent
from my_project.schemas.state import SupportState, StateUpdate
from my_project.schemas.vision import VisionUpdate
from my_project.workflow.stages import apply_update, apply_vision_update, next_stage, get_allowed_tools
from my_project.workflow.actions import decide_next_action
from my_project.vision.qwen import analyze_image_qwen, image_to_data_url
from my_project.vision.mock import analyze_image_mock
from my_project.rag.loader import load_knowledge_chunks
from my_project.rag.retriever import search_knowledge


class RegressionTests(unittest.TestCase):
    def extract(self, text, data):
        agent = create_extractor_agent('test-model')
        with patch('my_project.agents.extractor_agent.Runner.run_sync', return_value=SimpleNamespace(final_output=json.dumps(data))) as run:
            update = extract_state_update(agent, text)
            run.assert_called_once_with(agent, text)
        state = SupportState()
        apply_update(state, update)
        state.stage = next_stage(state)
        return state

    def test_case_1_extractor_response_to_state(self):
        state = self.extract("I'm Alice.", {'user_name': 'Alice'})
        self.assertEqual(state.user_name, 'Alice')
        self.assertEqual(state.stage, 'verify_identity')

    def test_case_2_extractor_response_to_state(self):
        state = self.extract("I'm Alice. My Anker Prime Charger (250W, 6 Ports, GaNPrime) won't charge.", {'user_name': 'Alice', 'product': 'Anker Prime Charger (250W, 6 Ports, GaNPrime)', 'issue': "won't charge"})
        self.assertEqual((state.user_name, state.product, state.issue, state.stage), ('Alice', 'Anker Prime Charger (250W, 6 Ports, GaNPrime)', "won't charge", 'verify_identity'))

    def test_case_3_real_image_mocked_qwen_transport(self):
        image = str(Path(entry.__file__).parent / 'test_images/charging_contacts.png')
        data = dict(dock_visible=True, indicator_on=True, contacts_dirty=True, robot_on_dock=False, observation='Visible contacts.')
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(data)))])
        update = analyze_image_qwen(image, client)
        self.assertIsInstance(update, VisionUpdate)
        state = SupportState()
        apply_vision_update(state, update)
        self.assertTrue(state.image_received)
        for key in ('dock_visible', 'indicator_on', 'contacts_dirty', 'robot_on_dock'):
            self.assertEqual(getattr(state, key), data[key])
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request['model'], 'qwen3-vl-plus')
        self.assertEqual(request['messages'][0]['content'][0]['image_url']['url'], image_to_data_url(image))
        self.assertTrue(image_to_data_url(image).startswith('data:image/png;base64,'))

    def test_case_4_action_and_existing_preconditions(self):
        state = SupportState(issue="won't charge", indicator_on=True, contacts_dirty=True)
        self.assertEqual(decide_next_action(state), 'clean_charging_contacts')
        state.indicator_on = False
        self.assertEqual(decide_next_action(state), 'check_dock_power')
        state.issue = None
        self.assertEqual(decide_next_action(state), 'continue_diagnosis')
        for issue in ('charging problem', "battery doesn't seem to be receiving power", 'CHARGING problem'):
            with self.subTest(issue=issue):
                state.issue = issue
                self.assertEqual(decide_next_action(state), 'check_dock_power')
                state.indicator_on = True
                self.assertEqual(decide_next_action(state), 'clean_charging_contacts')
                state.indicator_on = False
        state.issue = 'brush is stuck'
        self.assertEqual(decide_next_action(state), 'continue_diagnosis')

    def test_case_5_context_and_permissions(self):
        state = SupportState(user_name='Alice', customer_id='customer-1', identity_verified=True, product='Anker Prime Charger (250W, 6 Ports, GaNPrime)', issue="won't charge", stage='diagnose', image_received=True, indicator_on=True, contacts_dirty=True)
        tools, names = get_allowed_tools(state)
        turn = TurnContext(
            user_input="My Anker Prime Charger (250W, 6 Ports, GaNPrime) won't charge.",
            image_path="test.png",
            vision_update=VisionUpdate(indicator_on=True, contacts_dirty=True),
            retrieved_knowledge='KNOWLEDGE SENTINEL',
            next_action=decide_next_action(state),
            allowed_tools=tools,
            allowed_tool_names=names,
        )
        model_context = build_model_context(state, turn, [], [])
        agent = create_support_agent(model_context, 'test-model', tools)
        self.assertIsInstance(agent, Agent)
        for item in ('user_name: Alice', 'stage: diagnose', 'contacts_dirty: True', 'clean_charging_contacts', 'KNOWLEDGE SENTINEL'):
            self.assertIn(item, agent.instructions)
        self.assertEqual([t.name for t in agent.tools], names)
        cases = [
            (SupportState(stage='identify_user'), []),
            (SupportState(user_name='Alice', stage='verify_identity'), ['verify_customer']),
            (SupportState(user_name='Alice', customer_id='c1', identity_verified=True, stage='identify_product'), ['get_owned_products']),
            (SupportState(user_name='Alice', customer_id='c1', identity_verified=True, stage='understand_issue'), []),
            (SupportState(user_name='Alice', customer_id='c1', identity_verified=True, stage='diagnose'), ['check_warranty', 'create_ticket']),
            (SupportState(user_name='Alice', customer_id='c1', identity_verified=True, stage='resolved'), []),
        ]
        for test_state, expected in cases:
            actual, names = get_allowed_tools(test_state)
            self.assertEqual(names, expected)
            self.assertEqual([t.name for t in actual], expected)

    def test_null_updates_do_not_erase_state(self):
        state = SupportState(user_name='Alice', indicator_on=False)
        apply_update(state, StateUpdate())
        apply_vision_update(state, VisionUpdate())
        self.assertEqual(state.user_name, 'Alice')
        self.assertIs(state.indicator_on, False)
        self.assertTrue(state.image_received)

    def test_mock_vision_consistent(self):
        update = analyze_image_mock('unused.png')
        self.assertTrue(update.indicator_on)
        self.assertIn('appears on', update.observation)

    def test_retrieval_ranking_and_format(self):
        chunks = [
            {'source': 'a.md', 'text': 'A', 'product_id': 'anker-prime-250w', 'rag_namespace': 'anker_prime_250w'},
            {'source': 'b.md', 'text': 'B', 'product_id': 'anker-prime-250w', 'rag_namespace': 'anker_prime_250w'},
        ]
        encoder = Mock()
        encoder.encode.side_effect = [[1., 0.], [0., 1.], [1., 0.]]
        with patch('my_project.rag.retriever.load_knowledge_chunks', return_value=chunks):
            result = search_knowledge('query', encoder, top_k=1, product_id='anker-prime-250w')
        self.assertEqual(result, '[Score: 1.000]\n[Source: b.md]\nB')
        self.assertTrue(any('## Single-port output' in c['text'] for c in load_knowledge_chunks()))

    def test_process_turn_complete_offline_and_uses_merged_state_for_action(self):
        embedding = Mock()
        session = SupportSession()
        session.state.customer_id = 'customer-1'
        session.state.identity_verified = True
        with patch.object(turn_processor, 'create_qwen_client'), patch.object(turn_processor, 'create_deepseek_model', return_value='test-model'), patch.object(turn_processor, 'extract_state_update', return_value=StateUpdate(user_name='Alice', product='Anker Prime Charger (250W, 6 Ports, GaNPrime)', issue="won't charge")), patch.object(turn_processor, 'analyze_image_qwen', return_value=VisionUpdate(indicator_on=True, contacts_dirty=True)), patch.object(turn_processor, 'create_embedding_model', return_value=embedding), patch.object(turn_processor, 'search_knowledge', return_value='RAG SENTINEL'), patch.object(turn_processor.Runner, 'run_sync', return_value=SimpleNamespace(final_output='FINAL SENTINEL')) as run, contextlib.redirect_stdout(io.StringIO()) as output:
            result = turn_processor.process_turn(
                session,
                "I'm Alice. My Anker Prime Charger (250W, 6 Ports, GaNPrime) won't charge.",
                str(Path(entry.__file__).parent / 'test_images/charging_contacts.png'),
            )
        agent = run.call_args.args[0]
        self.assertIn('clean_charging_contacts', agent.instructions)
        self.assertNotIn('continue_diagnosis', agent.instructions)
        self.assertIn('RAG SENTINEL', agent.instructions)
        self.assertIn('contacts_dirty: True', agent.instructions)
        self.assertEqual(result, 'FINAL SENTINEL')

if __name__ == '__main__':
    unittest.main()
