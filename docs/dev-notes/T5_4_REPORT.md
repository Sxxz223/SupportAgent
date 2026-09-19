# T5.4：Context Builder 与最小 Runtime Event

## 文件变更

- 新增 `context/__init__.py`、`context/builder.py`：统一 Model Context 构建层。
- 新增 `application/events.py`：定义最小 `RuntimeEvent`。
- 修改 `application/session.py`：Session 增加 events；提供 `record_event`；TurnContext 增加本轮 model_context。
- 修改 `application/turn_processor.py`：记录 Vision/RAG Event，调用 Builder，再创建 Main Agent。
- 修改 `tools/support_tools.py`：三个 Tool 在成功产生业务效果时记录 Event。
- 修改 `agents/support_agent.py`：删除分散的 State/Vision/RAG 拼接，仅消费 Builder 输出。
- 新增 `tests/test_context_builder.py`，扩展现有 Runtime Event 和回归测试。
- 更新 `AGENTS.md` 和本报告。

## Context Builder

输入为明确列出的程序数据：`SupportState`、当前 `TurnContext`、`RuntimeEvent` 序列和 Conversation History 序列。Builder 不接收 `SupportSession` 或 `AppContext`，也不修改任何输入。

输出是一段稳定的 Model Context，包含：

- Current Business State：user、product、issue、stage、warranty、ticket、attempted steps、resolved。
- Current Turn：本轮输入、是否有图片、next action、allowed tool names。
- Current-turn Evidence：仅本轮 VisionUpdate；无图片时明确说明本轮没有图片证据。
- Historical Visual Evidence：无本轮图片时选取最近一次 `vision_analyzed` 的小型观察摘要，并明确标记历史 turn 和“本轮未观察”。
- Retrieved Knowledge：仅本轮实际 RAG 结果，保留原 source 标记。
- Important Previous Actions：仅 product_found、warranty_checked、ticket_created；每种只保留最新一条，避免重复堆砌。
- Recent Conversation：最多上一组已完成 User/Assistant 消息，每条最多 500 字符。

明确不会进入 LLM 的信息：完整 Session 对象、AppContext/ToolContext、完整 Events 列表、未知/debug Event、完整 History、embedding vector、图片 Base64、client/model 对象及任意未被 Builder 白名单选择的动态字段。

## Runtime Event

结构为：

```python
RuntimeEvent(event_type: str, turn_index: int, data: dict[str, Any])
```

State 表示当前事实；Event 表示导致事实或重要运行结果的动作；History 表示 User/Assistant 对话；TurnContext 表示一次调用的临时计算；Model Context 是 Builder 为当前 LLM 决策筛选出的只读视图。

当前记录五种 Event：

- `product_found`：product。
- `warranty_checked`：product、warranty_status。
- `ticket_created`：ticket_id、product；幂等重复调用不重复记录。
- `vision_analyzed`：四个视觉布尔字段及短 observation；不含图片/Base64。
- `rag_retrieved`：query、去重后的 source 文件名；不含 vector 或全文。

## process_turn 与 Agent

编排顺序保持为 Extraction → State → Vision → State → Stage → RAG → next action → tools。随后新增明确一步：`build_model_context(...)`。Main Agent 工厂现在只接收 Model Context、model 和 allowed tools，不再自行拼接另一份 State Context。

Tool 仍通过 `AppContext` 修改同一个 Session State 并记录对应 Event。Tool 后 Stage 仍会重算。Tool Event 在下一轮 Builder 中成为 Important Previous Actions，最新 State 也会同时进入 Current Business State。

## 测试结果

运行 `.venv/bin/python -m unittest discover -s tests -v`：27 项全部通过。

新增与扩展覆盖：

- 当前 State 的 user/product/ticket 等事实进入 Context。
- ticket_created 以一条紧凑历史 Action 出现，没有重复 Event 堆砌。
- 无图片轮将最近视觉 observation 明确标成历史证据。
- 有图片轮只将本轮 VisionUpdate 标为 current-turn evidence。
- Tool 更新的 product/warranty/ticket 在下一轮 Context 可见，对应 Event 可见。
- AppContext、SupportSession、动态 secret 和 debug Event 不被序列化。
- Tool Event 与 State 修改一致；重复 ticket 不产生第二个 ticket_created Event。
- Vision/RAG Event 按最小 metadata 记录。
- 原 Text、RAG、Vision、Workflow、Tool、Session、History、资源生命周期测试继续通过。

## 未扩大处理的问题

- Event 保存在内存 list，没有数据库、Event Sourcing、持久化或 Trace UI。
- 没有长 History 自动摘要、动态 token budget 或高级 Context Compression；当前只用固定小窗口和简单去重。
- 外部 Tool transaction rollback、retry、Human approval 仍未实现。
- 高级 RAG、Vision confidence/TTL、Web 前端仍在 backlog。
- JSON parser robustness 保持现状。
- Runtime Event data 使用轻量约定，没有引入复杂 schema registry 或版本迁移机制。
