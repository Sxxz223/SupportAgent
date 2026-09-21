"""Validate focused-task changes and maintain auditable live-path history."""
from typing import Any


WAITING_STAGES = {"waiting_confirmation", "completed", "cancelled"}
PRIORITY_PHRASES = ("先处理", "优先处理", "切换到", "先看", "先帮我")
PREREQUISITE_WORDS = ("前置", "才能继续", "需要先")
SAFETY_WORDS = ("安全", "高温", "发热", "冒烟", "异味", "鼓包")


def _user_changed_priority(user_input: str) -> bool:
    return any(item in user_input for item in PRIORITY_PHRASES)


def _has_safety_priority(session) -> bool:
    fact = session.facts.get("safety_signals")
    if fact and fact.value not in (None, False, "", [], "无", "没有"):
        return True
    return False


def apply_focus_change(session, presentation: dict, user_input: str, reply: str) -> None:
    requested = presentation.get("focusTaskId")
    if not requested or requested not in session.service_tasks:
        requested = session.focus_task_id or next(iter(session.service_tasks), None)
    current = session.focus_task_id
    if current and requested != current:
        current_stage = session.service_tasks.get(current, {}).get("stage")
        reason = presentation.get("focusChangeReason", "")
        allowed = (
            current_stage in WAITING_STAGES
            or _user_changed_priority(user_input)
            or _has_safety_priority(session)
            or any(word in reason for word in PREREQUISITE_WORDS)
        )
        explained = bool(reason) and reason in reply
        if not allowed or not explained:
            requested = current
            presentation["focusChanged"] = False
            presentation.pop("focusChangeReason", None)
            presentation["focusPath"] = session.focus_path
            presentation["plan"] = session.focus_plan
        else:
            presentation["focusChanged"] = True
            session.focus_history.append({
                "turnId": f"turn_{session.turn_index:03d}",
                "from": current, "to": requested, "reason": reason,
            })
    elif requested:
        presentation["focusChanged"] = False
    if requested:
        session.focus_task_id = requested
        presentation["focusTaskId"] = requested


def apply_live_plan(session, presentation: dict) -> None:
    path = presentation.get("focusPath")
    if isinstance(path, dict):
        session.focus_path = path
    plan = presentation.get("plan")
    if not isinstance(plan, dict):
        return
    old_steps = session.focus_plan.get("steps", [])
    new_steps = plan.get("steps", [])
    old_ids = [item.get("id") for item in old_steps]
    new_ids = [item.get("id") for item in new_steps]
    if old_ids and old_ids != new_ids:
        added = [item for item in new_ids if item not in old_ids]
        removed = [item for item in old_ids if item not in new_ids]
        reordered = not added and not removed and old_ids != new_ids
        if not plan.get("revision_note"):
            if added:
                plan["revision_note"] = "根据新信息增加了后续检查"
            elif removed:
                plan["revision_note"] = "已跳过不再需要的步骤"
            elif reordered:
                plan["revision_note"] = "根据新信息调整了处理顺序"
        session.path_history.append({
            "turnId": f"turn_{session.turn_index:03d}",
            "focusTaskId": session.focus_task_id,
            "before": old_ids, "after": new_ids,
            "added": added, "removed": removed, "reordered": reordered,
            "reason": plan.get("revision_note"),
        })
    session.focus_plan = plan
