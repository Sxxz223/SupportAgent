"""Program-owned task lifecycle gates for the service workspace."""
from typing import Any


STAGE_ORDER = {
    "confirmed": 0,
    "collecting": 1,
    "information_ready": 2,
    "judgement_formed": 3,
    "solution_provided": 4,
    "waiting_confirmation": 5,
    "completed": 6,
}

COMPLETION_INPUTS = {
    "已经解决", "问题已解决", "确认解决", "可以结束", "solved", "resolved",
}


def _record(session, action: str, task_id: str, **details: Any) -> None:
    session.task_history.append({
        "turnId": f"turn_{session.turn_index:03d}",
        "caseVersion": session.case_version + 1,
        "action": action,
        "taskId": task_id,
        **details,
    })


def _completion_confirmed(user_input: str, task_id: str) -> bool:
    normalized = user_input.strip().casefold()
    return normalized in COMPLETION_INPUTS or normalized == f"task_complete:{task_id}".casefold()


def _normalize_transition(session, update: dict, user_input: str) -> dict | None:
    task_id = update["taskId"]
    previous = session.service_tasks.get(task_id)
    requested = update["stage"]
    if previous is None:
        if requested in {"completed", "cancelled", "waiting_confirmation"}:
            requested = "confirmed"
        return {**update, "stage": requested}

    current = previous.get("stage", "confirmed")
    if requested == "cancelled":
        return None
    if requested == "completed" and not _completion_confirmed(user_input, task_id):
        requested = "waiting_confirmation" if STAGE_ORDER.get(current, 0) >= 4 else current
    if requested == "waiting_confirmation" and STAGE_ORDER.get(current, 0) < 4:
        requested = current
    if requested in STAGE_ORDER and current in STAGE_ORDER:
        if STAGE_ORDER[requested] < STAGE_ORDER[current] and not update.get("revisionReason"):
            requested = current
    return {**update, "stage": requested}


def propose_task_change(session, change: dict) -> None:
    session.pending_task_change = change


def confirm_task_change(session, user_input: str) -> bool:
    change = session.pending_task_change
    if not isinstance(change, dict):
        return False
    change_id = change.get("changeId", "change")
    if user_input.strip().casefold() != f"task_change_confirm:{change_id}".casefold():
        return False
    action = change.get("action")
    source_ids = change.get("sourceTaskIds", [])
    candidates = change.get("candidateTasks", [])
    if action == "cancel":
        for task_id in source_ids:
            if task_id in session.service_tasks:
                session.service_tasks[task_id]["stage"] = "cancelled"
                session.service_tasks[task_id]["statusText"] = "已按你的要求停止处理"
                _record(session, "cancel", task_id)
    elif action == "rename" and len(source_ids) == 1 and candidates:
        task = session.service_tasks.get(source_ids[0])
        if task:
            old_name = task.get("name")
            task["name"] = candidates[0]["name"]
            _record(session, "rename", source_ids[0], oldName=old_name, newName=task["name"])
    elif action in {"split", "merge"}:
        inherited_stage = "confirmed"
        for task_id in source_ids:
            task = session.service_tasks.get(task_id)
            if task and task.get("stage") in STAGE_ORDER:
                if STAGE_ORDER[task["stage"]] > STAGE_ORDER[inherited_stage]:
                    inherited_stage = task["stage"]
                task["stage"] = "cancelled"
                task["statusText"] = "已调整为新的任务安排"
                _record(session, action, task_id, boundary="source")
        for candidate in candidates:
            task_id = candidate["taskId"]
            session.service_tasks[task_id] = {
                "taskId": task_id, "name": candidate["name"],
                "stage": candidate.get("stage", inherited_stage),
                "statusText": candidate.get("statusText", "已根据现有信息建立"),
            }
            _record(session, action, task_id, boundary="candidate")
    elif action == "add":
        for candidate in candidates:
            task_id = candidate["taskId"]
            session.service_tasks[task_id] = {
                "taskId": task_id, "name": candidate["name"],
                "stage": candidate.get("stage", "confirmed"),
                "statusText": candidate.get("statusText", "已加入处理"),
            }
            _record(session, "add", task_id)
    else:
        return False
    session.pending_task_change = None
    return True


def apply_task_updates(
    session, updates: list[dict], user_input: str, allow_new_tasks: bool,
) -> list[dict]:
    applied: list[dict] = []
    for raw in updates:
        task_id = raw["taskId"]
        if task_id not in session.service_tasks and not allow_new_tasks:
            continue
        update = _normalize_transition(session, raw, user_input)
        if update is None:
            continue
        previous = session.service_tasks.get(task_id, {})
        merged = {**previous, **update}
        if previous != merged:
            _record(
                session, "update" if previous else "create", task_id,
                previousStage=previous.get("stage"), newStage=merged.get("stage"),
                reason=update.get("revisionReason"),
            )
        session.service_tasks[task_id] = merged
        applied.append(merged)
    return applied
