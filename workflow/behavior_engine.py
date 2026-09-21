"""Session-level observation and personified proactive behavior.

This layer is deliberately separate from business diagnosis.  It may speak,
show presence, or stay quiet, but it cannot mutate facts, tasks, or decisions.
"""
from __future__ import annotations

import time
from uuid import uuid4


INTRO_DELAY_SECONDS = 2.0
EVENT_TTL_SECONDS = 45.0


def _identity(session) -> tuple[str, int]:
    return f"turn_{session.turn_index:03d}", session.case_version


def _remove_superseded(session) -> None:
    session.proactive_events[:] = [
        event for event in session.proactive_events
        if event.get("eventType") not in {"proactive_message", "interaction_update"}
        and event.get("source") != "behavior_engine"
    ]


def _queue_message(session, *, content: str, emoji: str, label: str,
                   category: str, delay: float = 0.0) -> None:
    now = time.time()
    turn_id, case_version = _identity(session)
    version = int(session.behavior_state.get("activityVersion", 0))
    common = {
        "turnId": turn_id, "caseVersion": case_version,
        "activityVersion": version, "source": "behavior_engine",
        "deliverAt": now + delay, "expiresAt": now + delay + EVENT_TTL_SECONDS,
    }
    session.proactive_events.extend([
        {"eventType": "agent_state", "emoji": emoji, "label": label, **common},
        {
            "eventType": "proactive_message", "id": f"behavior-{uuid4().hex[:10]}",
            "content": content, "category": category,
            "agentState": {"emoji": emoji, "label": label}, **common,
        },
    ])
    session.behavior_state["lastProactiveCategory"] = category
    session.behavior_state["proactiveCount"] = int(
        session.behavior_state.get("proactiveCount", 0)
    ) + 1


def apply_behavior_decision(session, decision: dict) -> None:
    """Validate and enqueue a model-selected social action."""
    action = decision.get("action", "stay_silent")
    if action == "stay_silent":
        return
    content = str(decision.get("content", "")).strip()
    if not content:
        return
    _queue_message(
        session, content=content[:160], emoji=str(decision.get("emoji") or "🙂")[:8],
        label=str(decision.get("label") or "陪着你")[:24], category=action,
    )


def observe_activity(session, activity: str, *, detail: str | None = None) -> None:
    """Record a UI observation and decide whether the Agent should act."""
    state = session.behavior_state
    now = time.time()
    if activity == "focus" and state.get("leftAt"):
        state["secondsAway"] = max(0, round(now - float(state["leftAt"]), 1))
    elif activity == "leave":
        state["leftAt"] = now
    state["activityVersion"] = int(state.get("activityVersion", 0)) + 1
    state["lastActivity"] = activity
    state["lastActivityAt"] = now
    if detail:
        state["lastActivityDetail"] = detail[:120]
    _remove_superseded(session)

    if (
        activity == "session_created"
        and not state.get("introductionShown")
        and not state.get("introductionScheduled")
    ):
        _queue_message(
            session,
            content=("你好，我是 Anker 智能服务助手。你可以直接描述遇到的问题，"
                     "也可以发产品或故障照片；我会帮你理清多个需求，并跟着实际情况调整解决路径。"),
            emoji="👋", label="很高兴认识你", category="introduction",
            delay=INTRO_DELAY_SECONDS,
        )
        state["introductionScheduled"] = True
    elif activity == "image_selected":
        _queue_message(
            session, content="收到图片了，发给我后我会先看清关键位置，再和你确认识别结果。",
            emoji="👀", label="认真看你发来的信息", category="acknowledgement",
        )


def event_is_current(session, event: dict) -> bool:
    """Reject a scheduled action when later user activity made it stale."""
    expected = event.get("activityVersion")
    return expected is None or expected == session.behavior_state.get("activityVersion", 0)
