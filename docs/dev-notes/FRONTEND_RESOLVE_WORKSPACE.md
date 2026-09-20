# Dynamic support workspace

The customer page starts with an open help request. It does not show a solution path, request identity, or request order data before the customer describes a problem.

The frontend never derives a path from `stage`. It renders a path only when the Agent returns `plan.steps`. Each later response may replace the full plan so the Agent can add, remove, reorder, or complete nodes after learning new facts.

The optional response contract is:

```json
{
  "reply": "你说的充不上更接近哪种情况？",
  "stage": "diagnose",
  "interaction": {
    "type": "choice",
    "options": [
      { "id": "no_input", "label": "充电宝自己充不进电" },
      { "id": "no_output", "label": "充电宝不能给其他设备充电" }
    ]
  },
  "plan": {
    "steps": [
      { "id": "symptom", "title": "确认故障现象", "status": "current" },
      { "id": "risk", "title": "判断故障与风险", "status": "pending" }
    ],
    "progress": 20,
    "revision_note": "根据刚才的补充，改为排查输出中断"
  },
  "facts_update": { "device": "充电宝" }
}
```

`interaction.type` controls the next input: `choice`, `image`, `text`, `confirm`, or `none`. The image picker appears only for `image`; `image_prompt` tells the customer what to photograph. Older responses containing only `reply` and `stage` remain valid and display as conversation without an invented path.

Order, warranty, batch, firmware, and known-issue lookup belong after fault and risk assessment when the Agent decides that service fulfillment needs them. Only the customer can move a 99 percent plan to 100 percent by confirming that the problem is resolved.
