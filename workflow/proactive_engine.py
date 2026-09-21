"""Deterministic guardrails for limited proactive communication."""
from __future__ import annotations


WAITING_MARKERS = (
    "稍等", "等我", "我去", "我现在去", "正在找", "正在换", "正在拍", "我先试",
)


def apply_waiting_and_proactive_state(session, presentation: dict, user_input: str) -> None:
    """Recognize an explicit wait and provide one useful fallback message."""
    waiting = any(marker in user_input for marker in WAITING_MARKERS)
    session.interaction_state = {
        "status": "waiting_for_user_action" if waiting else "ready",
        "turnId": f"turn_{session.turn_index:03d}",
    }
    if not waiting or not session.focus_task_id or presentation.get("proactiveMessages"):
        return
    emotion = presentation.get("emotionState", {}).get("state", "neutral")
    delay = 2 if emotion == "frustrated" else 3 if emotion == "anxious" else 5
    presentation["proactiveMessages"] = [{
        "id": f"wait-{session.turn_index:03d}",
        "content": "前面已经确认的信息都保留着，完成后不用重新描述。",
        "category": "reassurance" if emotion in {"frustrated", "anxious"} else "supplement",
        "priority": 1,
        "delaySeconds": delay,
        "expiresInSeconds": 20,
    }]
