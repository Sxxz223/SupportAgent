"""Communication-only customer emotion tracking."""
from __future__ import annotations

from typing import Any


EMOTION_LEVEL = {
    "calm": 0,
    "neutral": 0,
    "confused": 1,
    "anxious": 2,
    "frustrated": 3,
}


def _text_signal(user_input: str) -> str | None:
    """Provide a conservative fallback when the model omits emotionState."""
    text = user_input.strip().lower()
    if any(marker in text for marker in ("搞不懂", "不明白", "什么意思", "怎么操作", "看不懂")):
        return "confused"
    if any(marker in text for marker in ("着急", "急用", "赶时间", "明天要用", "马上要用", "担心")):
        return "anxious"
    if any(marker in text for marker in ("到底能不能", "怎么还", "太离谱", "很生气", "烦死", "投诉")):
        return "frustrated"
    if any(marker in text for marker in ("谢谢", "明白了", "好了", "解决了", "可以了")):
        return "calm"
    return None


def apply_emotion_state(session: Any, presentation: dict, user_input: str) -> dict[str, str]:
    """Normalize one emotion update without touching any business state."""
    previous = session.emotion_history[-1]["state"] if session.emotion_history else "neutral"
    proposed = presentation.get("emotionState") or {}
    current = proposed.get("state") or _text_signal(user_input) or previous
    if current not in EMOTION_LEVEL:
        current = previous

    delta = EMOTION_LEVEL[current] - EMOTION_LEVEL.get(previous, 0)
    trend = "worsening" if delta > 0 else "improving" if delta < 0 else "stable"
    normalized = {"state": current, "trend": trend}
    presentation["emotionState"] = normalized
    session.emotion_history.append({
        "turn_index": session.turn_index,
        **normalized,
    })
    session.emotion_history[:] = session.emotion_history[-20:]
    return normalized
