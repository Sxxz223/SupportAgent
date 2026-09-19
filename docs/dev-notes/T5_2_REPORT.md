# T5.2：多轮 Session 与 State 生命周期

## 文件变更

- 新增 `application/session.py`：定义 `SupportSession` 和 `TurnContext`。
- 修改 `application/turn_processor.py`：统一入口改为接收 Session，维护轮次和 History。
- 修改 `agents/support_agent.py`：最小调整视觉 Context，区分本轮观察和历史事实。
- 修改 `providers/deepseek.py`、`providers/qwen.py`、`rag/embeddings.py`：缓存重资源工厂返回值。
- 修改 `main.py`：改为复用同一个 Session 的多轮 CLI。
- 修改 `tests/test_turn_processor.py`、`tests/test_refactor.py`：加入多轮、视觉来源、调用顺序、History 和资源生命周期回归。
- 更新 `AGENTS.md`：记录新的模块职责和编排约束。

## 生命周期职责

`SupportSession` 持有一个固定的 `SupportState`、基础 `history` 和 `turn_index`。State 仍是跨轮结构化业务事实，不由聊天记录代替。History 使用简单字典记录成功完成轮次的 `turn_index`、`role` 和 `content`。

`TurnContext` 仅在一次 `process_turn` 调用中存在，保存 `user_input`、`image_path`、本轮 `VisionUpdate`、RAG 结果、`next_action` 和允许工具。它不会写入 Session，也不会把临时检索结果或工具对象塞入长期 State。

## process_turn 顺序

1. `session.turn_index += 1`，取得同一个 `session.state`。
2. 创建本轮 `TurnContext`。
3. 复用 DeepSeek model，执行现有 Extractor，合并 `StateUpdate`。
4. 本轮有图片时复用 Qwen client，执行现有 Vision，合并 `VisionUpdate`；无图片时完全跳过。
5. 在所有感知更新完成后计算 Stage。
6. diagnose 阶段复用 embedding model，执行原 RAG。
7. 根据完整 State 计算 `next_action`。
8. 根据 Stage 获取允许工具。
9. 将 State、当前/历史 Vision 来源、RAG、动作与工具传入原 Support Agent。
10. 执行 Main Agent。
11. 成功后将本轮 User/Assistant 两条消息写入 History，返回回复。

## Vision 来源

视觉布尔事实仍按现有设计保存在 `SupportState`，所以后续无图片轮可以使用历史事实进行业务判断。当前轮的 `VisionUpdate` 仅存在于 `TurnContext`。Agent Context 现在明确显示：

- 有图片：标记为本轮已分析图片，并包含本轮 `observation`。
- 无图片：明确写明本轮没有图片，State 中的视觉字段来自历史观察，不得描述为本轮看到。

历史 `observation` 没有存入 State，因此不会在下一轮误带为当前图片描述。未实现 TTL、置信度衰减或自动失效。

## 重资源复用

三个无参数工厂使用单实例缓存：DeepSeek `AsyncOpenAI`/模型封装、Qwen `OpenAI` client、SentenceTransformer。首次实际需要时初始化，进程生命周期内复用。Qwen 仍只在图片轮首次创建，embedding 仍只在 diagnose 轮首次加载。模型、Provider、endpoint、模型名称和参数均未改变。

## 验证

运行 `.venv/bin/python -m unittest discover -s tests -v`：15 项全部通过。

覆盖内容包括：

- 三轮状态演进：Alice → legacy demo product (removed) → receiving power，Stage 顺序正确。
- 三轮 `SupportState` 对象 identity 不变；History 为 6 条、轮次及角色顺序正确。
- 第三轮执行 RAG，Stage 对应工具权限正确。
- 无图片轮不创建或调用 Qwen。
- 图片更新先于 Stage、RAG、动作和工具权限决策。
- 下一轮无图片时保留视觉事实，但 Context 明确其历史来源，且不包含上一轮 observation。
- CLI 两轮调用复用同一个 Session。
- DeepSeek、Qwen 和 embedding 工厂各调用两次时，底层构造器各只运行一次。
- 原有 State、Vision、动作、权限、RAG 和 Context 回归继续通过。

## 未扩大处理的问题

- Tool 仍为 mock，结果不形成完整状态闭环。
- 外部调用失败没有事务回滚；当前实现会保留失败前已合并的 State，且已开始的 `turn_index` 不回退，History 只记录成功完成的轮次。
- 未实现视觉 confidence、TTL、事实过期或冲突解决。
- 未升级 RAG、JSON parser robustness。
- Session 仅在内存中，不做数据库或文件持久化。
- 未增加 Web 前端。
- History 当前仅作会话记录，不注入 Agent Prompt；Agent 仍以结构化 State 为业务事实来源。
