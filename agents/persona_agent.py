"""A narrow Agent that decides social presence without changing business state."""
from __future__ import annotations

import json

from agents import Agent, Runner

from ..providers.deepseek import create_deepseek_model


ALLOWED_ACTIONS = {"stay_silent", "reassure", "encourage", "small_talk", "offer_help"}


def _context(session, activity: str) -> str:
    recent = [
        {"role": item.get("role"), "content": str(item.get("content", ""))[:240]}
        for item in session.history[-4:]
    ]
    tasks = [
        {"name": item.get("name"), "stage": item.get("stage"),
         "status": item.get("statusText")}
        for item in session.service_tasks.values()
    ]
    return json.dumps({
        "observedActivity": activity,
        "recentConversation": recent,
        "tasks": tasks,
        "interactionStatus": session.interaction_state.get("status", "ready"),
        "previousProactiveCategory": session.behavior_state.get("lastProactiveCategory"),
        "proactiveCount": session.behavior_state.get("proactiveCount", 0),
        "secondsAway": session.behavior_state.get("secondsAway"),
    }, ensure_ascii=False)


def decide_personified_behavior(session, activity: str) -> dict:
    """Let the model choose one bounded social action; fail closed to silence."""
    agent = Agent(
        name="Anker Persona Observer",
        model=create_deepseek_model(),
        instructions="""
你是 Anker 智能服务助手的拟人化观察层。你观察会话，但绝不能改变产品事实、诊断、任务、解决路径或操作卡片。
根据给定上下文选择一次动作：stay_silent、reassure、encourage、small_talk、offer_help。
大多数普通停顿应保持安静。只有能减轻焦虑、自然维持陪伴感或确实有帮助时才说话。闲聊必须贴近当前语境，不能打断用户输入，不能假装知道未提供的信息，不能重复刚说过的话。
若说话，content 只写一句自然中文；emoji 和 label 表达助手自身的温暖情绪，不得使用“处理中、检查中、加载中”等系统状态。
只返回 JSON：{"action":"stay_silent","content":"","emoji":"🙂","label":"安静陪着你"}
""",
    )
    try:
        result = Runner.run_sync(agent, _context(session, activity), max_turns=1)
        data = json.loads(result.final_output)
        action = data.get("action")
        content = str(data.get("content", "")).strip()
        if action not in ALLOWED_ACTIONS or (action != "stay_silent" and not content):
            return {"action": "stay_silent"}
        return {
            "action": action, "content": content[:160],
            "emoji": str(data.get("emoji") or "🙂")[:8],
            "label": str(data.get("label") or "陪着你")[:24],
        }
    except Exception:
        return {"action": "stay_silent"}
