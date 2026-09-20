# Service workspace contract

The customer interface has four stable regions: a multi-task status bar, one focused-task panel, one conversation stream, and one bottom action panel. The frontend owns these regions, the safe component set, stage-to-progress mapping, final confirmation rule, and proactive-message throttling. The Agent owns all changing content and decisions.

## Formal turn response

```json
{
  "reply": "我先确认一下当前连接状态。",
  "taskDecision": { "type": "single" },
  "taskUpdates": [
    { "taskId": "charging", "name": "充电异常", "stage": "collecting", "statusText": "正在确认连接状态" }
  ],
  "focusTaskId": "charging",
  "focusChanged": false,
  "focusPath": {
    "currentState": "正在定位充电异常原因",
    "knownFacts": ["换线后仍无效"],
    "currentJudgement": "暂时无法确定是否为接口问题",
    "nextDirection": "确认当前使用接口"
  },
  "interaction": {
    "type": "choice_image",
    "question": "当前连接的是哪个接口？",
    "options": [{ "id": "c1", "label": "USB-C 1", "value": "USB-C 1" }],
    "image": { "enabled": true, "label": "拍给 AI 看", "target": "当前线材连接位置", "fields": ["接口类型", "输出功率"] }
  },
  "agentState": { "emoji": "thinking" }
}
```

Supported interaction types are `choice`, `choice_image`, `text`, `confirm`, `split_confirm`, `image_confirm`, `partial_reshoot`, and `none`. Formal tasks are not created from a proposed split until the customer confirms it.

Task progress is fixed by the frontend:

| Stage | Progress |
|---|---:|
| confirmed | 10% |
| collecting | 30% |
| information_ready | 50% |
| judgement_formed | 70% |
| solution_provided | 90% |
| waiting_confirmation | 99% |
| completed | 100% |

The Agent never supplies arbitrary percentages. A task reaches `completed` only after explicit customer confirmation.

## Vision context

`POST /chat/multimodal` receives `visual_context` with the current task ID, interaction type, requested target, and requested fields. The server stores it in the session and gives it to the Agent together with the image analysis. The response may include recognized and unclear fields. Recognized values remain available when the next interaction asks for a partial reshoot.

## Proactive messages

`GET /session/{session_id}/events` is an SSE stream. The Agent may queue at most one proactive message per formal turn. The frontend delays it briefly, applies a cooldown, and cancels pending display as soon as the customer types, clicks, or uploads. Proactive messages never create tasks or required actions; those belong only in the bottom action panel.
