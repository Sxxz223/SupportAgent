"""Coordinate one support turn using the existing domain modules."""
import json
import re

from agents import Runner

from .context import AppContext
from .session import SupportSession, TurnContext
from ..agents.extractor_agent import create_extractor_agent, extract_state_update
from ..agents.support_agent import create_support_agent
from ..context.builder import build_model_context
from ..providers.deepseek import create_deepseek_model
from ..providers.qwen import create_qwen_client
from ..rag.embeddings import create_embedding_model
from ..rag.retriever import search_knowledge
from ..trace.recorder import TraceRecorder, snapshot_state
from ..vision.qwen import analyze_image_qwen
from ..workflow.actions import decide_next_action
from ..workflow.stages import apply_update, apply_vision_update, next_stage, get_allowed_tools

MAX_AGENT_STEPS = 5
TASK_DECISIONS = {"single", "clarify", "propose_split", "confirmed"}
INTERACTION_TYPES = {
    "choice", "choice_image", "image", "text", "confirm", "split_confirm",
    "completion_confirm", "image_confirm", "partial_reshoot", "none",
}
TASK_STAGES = {
    "confirmed", "collecting", "information_ready", "judgement_formed",
    "solution_provided", "waiting_confirmation", "completed", "cancelled",
}
AGENT_STATES = {"idle", "thinking", "checking", "investigating", "found", "insight", "done_step", "completed", "resolved"}
PLAN_STATES = {"done", "current", "pending"}


def _parse_agent_output(raw: str) -> tuple[str, dict]:
    """Separate customer copy from the Agent-owned UI description."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return raw, {}
    if not isinstance(payload, dict) or not isinstance(payload.get("reply"), str):
        return raw, {}
    presentation = {
        key: payload[key] for key in (
            "interaction", "taskDecision", "taskUpdates", "focusTaskId",
            "focusChanged", "focusChangeReason", "focusPath", "plan", "agentState",
            "emotionState", "visionResult",
        )
        if isinstance(payload.get(key), dict)
        or isinstance(payload.get(key), list)
    }
    decision = presentation.get("taskDecision")
    if decision and decision.get("type") not in TASK_DECISIONS:
        presentation.pop("taskDecision", None)
    interaction = presentation.get("interaction")
    if interaction and interaction.get("type") not in INTERACTION_TYPES:
        presentation.pop("interaction", None)
    tasks = presentation.get("taskUpdates")
    if tasks is not None:
        presentation["taskUpdates"] = [
            task for task in tasks
            if isinstance(task, dict)
            and isinstance(task.get("taskId"), str)
            and isinstance(task.get("name"), str)
            and task.get("stage") in TASK_STAGES
            and isinstance(task.get("statusText"), str)
        ]
    agent_state = presentation.get("agentState")
    if agent_state and agent_state.get("emoji") not in AGENT_STATES:
        presentation.pop("agentState", None)
    plan = presentation.get("plan")
    if plan:
        steps = plan.get("steps")
        if not isinstance(steps, list):
            presentation.pop("plan", None)
        else:
            valid_steps = [
                step for step in steps
                if isinstance(step, dict)
                and isinstance(step.get("id"), str)
                and isinstance(step.get("title"), str)
                and step.get("status") in PLAN_STATES
            ]
            if not valid_steps or sum(step["status"] == "current" for step in valid_steps) > 1:
                presentation.pop("plan", None)
            else:
                plan["steps"] = valid_steps
    proactive = payload.get("proactiveMessages")
    if isinstance(proactive, list):
        presentation["proactiveMessages"] = [item for item in proactive if isinstance(item, dict)]
    return payload["reply"], presentation


def _merge_service_view(session: SupportSession, presentation: dict, user_input: str) -> None:
    decision_type = presentation.get("taskDecision", {}).get("type")
    if decision_type == "propose_split":
        session.pending_task_change = "split"
        presentation["taskUpdates"] = []
        presentation.pop("focusTaskId", None)
        presentation.pop("focusPath", None)
        presentation.pop("plan", None)
    elif decision_type == "confirmed" and session.pending_task_change == "split":
        normalized = user_input.strip().lower()
        if normalized in {"split", "分开处理", "分别处理"}:
            session.pending_task_change = None
        elif normalized in {"keep_one", "保持一个任务", "合并处理"}:
            session.pending_task_change = None
            presentation["taskUpdates"] = presentation.get("taskUpdates", [])[:1]
        else:
            presentation["taskUpdates"] = []
            presentation.pop("focusTaskId", None)
            presentation.pop("focusPath", None)
            presentation.pop("plan", None)
    for task in presentation.get("taskUpdates", []):
        task_id = task.get("taskId")
        if task_id:
            session.service_tasks[task_id] = {**session.service_tasks.get(task_id, {}), **task}
    focus_id = presentation.get("focusTaskId")
    if not focus_id and session.service_tasks:
        focus_id = session.focus_task_id or next(iter(session.service_tasks))
        presentation["focusTaskId"] = focus_id
    if focus_id:
        session.focus_task_id = focus_id
    if isinstance(presentation.get("focusPath"), dict):
        session.focus_path = presentation["focusPath"]
    if isinstance(presentation.get("plan"), dict):
        session.focus_plan = presentation["plan"]


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
            if session.service_tasks:
                turn.model_context += "\n\nCurrent service workspace state:\n" + json.dumps({
                    "tasks": list(session.service_tasks.values()),
                    "focusTaskId": session.focus_task_id,
                    "focusPath": session.focus_path,
                    "plan": session.focus_plan,
                    "visionRequest": session.vision_request,
                }, ensure_ascii=False)
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
        final_output, session.presentation = _parse_agent_output(str(final_output))
        _merge_service_view(session, session.presentation, user_input)
        session.case_version += 1
        session.presentation["turnId"] = f"turn_{session.turn_index:03d}"
        session.presentation["caseVersion"] = session.case_version
        for message in session.presentation.pop("proactiveMessages", []):
            session.proactive_events.append({
                "turn_index": session.turn_index,
                "turnId": session.presentation["turnId"],
                "caseVersion": session.case_version,
                **message,
            })
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
