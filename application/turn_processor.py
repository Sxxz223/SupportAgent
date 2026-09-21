"""Coordinate one support turn using the existing domain modules."""
import json
import re
import time

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
from ..schemas.presentation import validate_presentation
from ..workflow.task_engine import apply_task_updates, confirm_task_change, propose_task_change
from ..workflow.focus_engine import apply_focus_change, apply_live_plan
from ..workflow.emotion_engine import apply_emotion_state

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


def _record_text_facts(session: SupportSession, update):
    safe_update = update.model_copy(deep=True)
    for key in ("user_name", "phone_last4", "order_no", "product", "issue"):
        value = getattr(update, key, None)
        if value is not None:
            session.upsert_fact(key, value, "user_text", confirmed=False)
    for key, fact in update.facts.items():
        accepted = session.upsert_fact(
            key, fact.value, "user_text", confirmed=False, kind=fact.kind,
            detect_conflict=True,
        )
        if not accepted:
            safe_update.facts.pop(key, None)
    return safe_update


FACT_LABELS = {
    "target_device": "正在连接的设备", "symptom": "当前表现",
    "current_port": "当前接口", "power_reading": "屏幕功率",
    "product_model": "产品型号", "safety_signals": "安全状况",
}


def _apply_fact_conflict_view(session: SupportSession, presentation: dict) -> str | None:
    if not session.pending_fact_conflicts:
        return None
    key, conflict = next(iter(session.pending_fact_conflicts.items()))
    label = FACT_LABELS.get(key, key)
    previous, incoming = conflict["previous"], conflict["incoming"]
    presentation["taskDecision"] = {"type": "clarify", "candidateTasks": []}
    presentation["interaction"] = {
        "type": "choice",
        "question": f"所以现在的{label}更接近哪一种？",
        "options": [
            {"id": "keep-previous", "label": str(previous), "value": str(previous)},
            {"id": "use-incoming", "label": str(incoming), "value": str(incoming)},
        ],
    }
    return f"我注意到你前后描述的{label}不太一样。只需要确认现在实际看到的情况。"


def _record_vision_facts(session: SupportSession, update) -> None:
    session.stage_vision_result(update.fields, update.reshoot_target)
    for key in ("dock_visible", "indicator_on", "contacts_dirty", "robot_on_dock", "observation"):
        value = getattr(update, key, None)
        if value is not None:
            session.upsert_fact(key, value, "image_analysis", confirmed=False)


def _apply_vision_result_view(session: SupportSession, presentation: dict) -> None:
    if not session.pending_vision_fields:
        return
    fields = list(session.pending_vision_fields.values())
    presentation["visionResult"] = {
        "fields": fields,
        **({"followUp": {"type": "partial_reshoot", "target": session.pending_reshoot_target}}
           if session.pending_reshoot_target else {}),
    }
    incomplete = [item for item in fields if item.get("status") != "recognized"]
    if incomplete:
        target = session.pending_reshoot_target or "、".join(item.get("label", item["key"]) for item in incomplete)
        presentation["interaction"] = {
            "type": "partial_reshoot",
            "question": "有一部分没有看清，只需要补拍模糊的位置。",
            "options": [],
            "image": {"enabled": True, "label": "补拍图片", "target": target, "fields": [item["key"] for item in incomplete]},
        }
    else:
        presentation["interaction"] = {
            "type": "image_confirm",
            "question": "这些识别结果是否正确？",
            "options": [
                {"id": "vision-confirm", "label": "识别正确", "value": "vision_confirm"},
                {"id": "vision-reject", "label": "有错误", "value": "vision_reject"},
            ],
        }


def _sync_confirmed_business_facts(session: SupportSession) -> None:
    state = session.state
    values = {
        "customer_id": state.customer_id,
        "identity_verified": state.identity_verified if state.identity_verified else None,
        "product_id": state.product_id,
        "warranty_status": state.warranty_status,
        "ticket_id": state.ticket_id,
    }
    for key, value in values.items():
        if value is not None:
            session.upsert_fact(key, value, "business_system", confirmed=True)


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
    presentation = validate_presentation(payload)
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
            current_count = sum(step["status"] == "current" for step in valid_steps)
            all_done = all(step["status"] == "done" for step in valid_steps)
            if not valid_steps or (current_count != 1 and not all_done):
                presentation.pop("plan", None)
            else:
                plan["steps"] = valid_steps
    return payload["reply"], presentation


def _merge_service_view(session: SupportSession, presentation: dict, user_input: str) -> None:
    for key, value in presentation.get("factsUpdate", {}).items():
        session.upsert_fact(
            key, value, "agent_extraction", confirmed=False,
            detect_conflict=True,
        )
    decision_type = presentation.get("taskDecision", {}).get("type")
    change = presentation.get("taskChange")
    if change and change.get("status") == "proposed":
        propose_task_change(session, change)
        presentation["taskUpdates"] = []
    change_confirmed = confirm_task_change(session, user_input)
    allow_new_tasks = not session.service_tasks or change_confirmed
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
            allow_new_tasks = True
        elif normalized in {"keep_one", "保持一个任务", "合并处理"}:
            session.pending_task_change = None
            presentation["taskUpdates"] = presentation.get("taskUpdates", [])[:1]
        else:
            presentation["taskUpdates"] = []
            presentation.pop("focusTaskId", None)
            presentation.pop("focusPath", None)
            presentation.pop("plan", None)
    presentation["taskUpdates"] = apply_task_updates(
        session, presentation.get("taskUpdates", []), user_input, allow_new_tasks,
    )


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
    # A new customer action invalidates every unsent event from the previous turn.
    session.proactive_events.clear()
    started_at = time.time()
    session.proactive_events.append({
        "eventType": "agent_state",
        "turn_index": session.turn_index,
        "turnId": f"turn_{session.turn_index:03d}",
        "caseVersion": session.case_version + 1,
        "state": "checking" if image_path else "thinking",
        "deliverAt": started_at,
        "expiresAt": started_at + 30,
    })
    state = session.state
    resolved_conflict = session.resolve_fact_conflict(user_input)
    if resolved_conflict:
        key, value = resolved_conflict
        state.diagnostic_facts[key] = value
    vision_confirmation = session.resolve_vision_confirmation(user_input)
    if vision_confirmation == "confirmed":
        for key, fact in session.facts.items():
            if fact.source == "image_confirmed":
                state.diagnostic_facts[key] = fact.value
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
        update = _record_text_facts(session, update)
        apply_update(state, update)

        if image_path:
            failed_stage = "vision"
            try:
                vision_before = snapshot_state(state) if recorder else {}
            except Exception:
                vision_before = {}
            vision_client = create_qwen_client()
            turn.vision_update = analyze_image_qwen(
                image_path, vision_client,
                visual_context=session.vision_request,
                existing_facts={key: fact.value for key, fact in session.facts.items()},
            )
            apply_vision_update(state, turn.vision_update)
            _record_vision_facts(session, turn.vision_update)
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
            if state.product and state.issue and not turn.retrieved_knowledge:
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
            if session.service_tasks or session.facts:
                turn.model_context += "\n\nCurrent service workspace state:\n" + json.dumps({
                    "facts": {
                        key: {
                            "value": fact.value, "source": fact.source,
                            "confirmed": fact.confirmed, "kind": fact.kind,
                        }
                        for key, fact in session.facts.items()
                    },
                    "tasks": list(session.service_tasks.values()),
                    "focusTaskId": session.focus_task_id,
                    "focusPath": session.focus_path,
                    "plan": session.focus_plan,
                    "visionRequest": session.vision_request,
                    "communicationState": (
                        session.emotion_history[-1] if session.emotion_history else None
                    ),
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
        _sync_confirmed_business_facts(session)
        final_output, session.presentation = _parse_agent_output(str(final_output))
        _merge_service_view(session, session.presentation, user_input)
        apply_focus_change(session, session.presentation, user_input, final_output)
        apply_live_plan(session, session.presentation)
        apply_emotion_state(session, session.presentation, user_input)
        _apply_vision_result_view(session, session.presentation)
        conflict_reply = _apply_fact_conflict_view(session, session.presentation)
        if conflict_reply:
            final_output = conflict_reply
        session.case_version += 1
        session.presentation["turnId"] = f"turn_{session.turn_index:03d}"
        session.presentation["caseVersion"] = session.case_version
        proactive_messages = session.presentation.pop("proactiveMessages", [])
        agent_state = session.presentation.get("agentState")
        if agent_state:
            session.proactive_events.append({
                "eventType": "agent_state",
                "turn_index": session.turn_index,
                "turnId": session.presentation["turnId"],
                "caseVersion": session.case_version,
                "state": agent_state["emoji"],
                "deliverAt": time.time(),
                "expiresAt": time.time() + 10,
            })
        for message in proactive_messages:
            delay = message.pop("delaySeconds", 3)
            expires = message.get("expiresInSeconds", 10)
            created_at = time.time()
            session.proactive_events.append({
                "eventType": "proactive_message",
                "turn_index": session.turn_index,
                "turnId": session.presentation["turnId"],
                "caseVersion": session.case_version,
                "deliverAt": created_at + delay,
                "expiresAt": created_at + delay + expires,
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
