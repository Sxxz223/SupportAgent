"""Coordinate one support turn using the existing domain modules."""
import re

from agents import Runner

from .context import AppContext
from .session import SupportSession, TurnContext
from support_agents.extractor_agent import create_extractor_agent, extract_state_update
from support_agents.support_agent import create_support_agent
from context.builder import build_model_context
from providers.deepseek import create_deepseek_model
from providers.qwen import create_qwen_client
from rag.embeddings import create_embedding_model
from rag.retriever import search_knowledge
from trace.recorder import TraceRecorder, snapshot_state
from vision.qwen import analyze_image_qwen
from workflow.actions import decide_next_action
from workflow.stages import apply_update, apply_vision_update, next_stage, get_allowed_tools

MAX_AGENT_STEPS = 5


def process_turn(
    session: SupportSession,
    user_input: str,
    image_path: str | None = None,
) -> str:
    """Advance one session turn and return the support Agent's response.

    Persistent facts live in session.state. Temporary perception, retrieval,
    action and tool values live only in the local TurnContext.
    """
    session.turn_index += 1
    state = session.state
    turn = TurnContext(user_input=user_input, image_path=image_path)
    try:
        recorder: TraceRecorder | None = TraceRecorder(
            session=session,
            user_input=user_input,
            has_image=image_path is not None,
        )
    except Exception:
        recorder = None

    failed_stage = "model_initialization"
    final_output: str | None = None
    try:
        model = create_deepseek_model()
        extractor_agent = create_extractor_agent(model)
        failed_stage = "text_extraction"
        update = extract_state_update(extractor_agent, user_input)
        if recorder:
            recorder.record_extraction(update)
        apply_update(state, update)

        if image_path:
            failed_stage = "vision"
            try:
                vision_before = snapshot_state(state) if recorder else {}
            except Exception:
                vision_before = {}
            vision_client = create_qwen_client()
            turn.vision_update = analyze_image_qwen(image_path, vision_client)
            apply_vision_update(state, turn.vision_update)
            try:
                vision_after = snapshot_state(state) if recorder else {}
            except Exception:
                vision_after = {}
            if recorder:
                recorder.record_vision(turn.vision_update, vision_before, vision_after)
            session.record_event(
                "vision_analyzed",
                dock_visible=turn.vision_update.dock_visible,
                indicator_on=turn.vision_update.indicator_on,
                contacts_dirty=turn.vision_update.contacts_dirty,
                robot_on_dock=turn.vision_update.robot_on_dock,
                observation=turn.vision_update.observation,
            )

            print("\n[VISION UPDATE]")
            print("dock_visible:", turn.vision_update.dock_visible)
            print("indicator_on:", turn.vision_update.indicator_on)
            print("contacts_dirty:", turn.vision_update.contacts_dirty)
            print("robot_on_dock:", turn.vision_update.robot_on_dock)
            print("observation:", turn.vision_update.observation)

        if recorder:
            recorder.record_perception_state(state)
        failed_stage = "workflow"
        state.stage = next_stage(state)

        print("\n[CURRENT STATE]")
        print("user_name:", state.user_name)
        print("customer_id:", state.customer_id)
        print("identity_verified:", state.identity_verified)
        print("product:", state.product)
        print("issue:", state.issue)
        print("stage:", state.stage)
        print("resolved:", state.resolved)

        support_result = None
        for step_index in range(1, MAX_AGENT_STEPS + 1):
            if state.stage == "diagnose" and not turn.retrieved_knowledge:
                failed_stage = "rag_retrieval"
                embedding_model = create_embedding_model()
                query = f"{state.product} {state.issue}"
                turn.retrieved_knowledge = search_knowledge(
                    query, embedding_model, product=state.product, product_id=state.product_id,
                )
                if recorder:
                    recorder.record_retrieval(query, turn.retrieved_knowledge)
                sources = list(dict.fromkeys(re.findall(
                    r"^\[Source: (.+?)\]$", turn.retrieved_knowledge, re.MULTILINE
                )))
                session.record_event("rag_retrieved", query=query, sources=sources)

            failed_stage = "workflow"
            turn.next_action = decide_next_action(state)
            turn.allowed_tools, turn.allowed_tool_names = get_allowed_tools(state)
            if recorder and step_index == 1:
                recorder.record_workflow_before_agent(
                    state.stage, turn.next_action, turn.allowed_tool_names
                )

            print(f"\n[AGENT STEP {step_index}]")
            print("Current stage:", state.stage)
            print("Allowed tools:", turn.allowed_tool_names)

            failed_stage = "context_builder"
            turn.model_context = build_model_context(
                state=state, turn=turn, events=session.events, history=session.history,
            )
            if recorder:
                recorder.record_context([
                    "current_business_state", "current_turn", "current_turn_evidence",
                    "historical_visual_evidence", "retrieved_knowledge",
                    "important_previous_actions", "recent_conversation",
                ])
            support_agent = create_support_agent(turn.model_context, model, turn.allowed_tools)
            failed_stage = "main_agent"
            if recorder:
                recorder.record_agent_called()
            step_state_before = snapshot_state(state)
            event_count_before = len(session.events)
            tool_count_before = len(recorder.trace.tool_calls) if recorder else 0
            support_result = Runner.run_sync(
                support_agent, user_input, context=AppContext(session=session),
            )
            state.stage = next_stage(state)
            tool_names = (
                [item.tool_name for item in recorder.trace.tool_calls[tool_count_before:]]
                if recorder else []
            )
            tool_or_event_occurred = bool(tool_names) or len(session.events) > event_count_before
            state_changed = step_state_before != snapshot_state(state)
            if recorder:
                recorder.record_agent_step(
                    step_index, step_state_before.get("stage", state.stage),
                    turn.next_action, turn.allowed_tool_names, step_state_before,
                    tool_names, snapshot_state(state),
                )
            if not tool_or_event_occurred or not state_changed:
                final_output = support_result.final_output
                break
            final_output = support_result.final_output

        if support_result is None:
            raise RuntimeError("Main Agent did not run")
        workflow_after_tools_action = decide_next_action(state)
        _, workflow_after_tools_names = get_allowed_tools(state)
        if recorder:
            recorder.record_workflow_after_tools(
                state.stage, workflow_after_tools_action, workflow_after_tools_names
            )
        if recorder:
            recorder.record_agent_reply(final_output)
        session.history.extend([
            {"turn_index": session.turn_index, "role": "user", "content": user_input},
            {"turn_index": session.turn_index, "role": "assistant", "content": final_output},
        ])
        return final_output
    except Exception as error:
        if recorder:
            recorder.fail(failed_stage, error)
        raise
    finally:
        if recorder:
            recorder.finish(state, final_output)
