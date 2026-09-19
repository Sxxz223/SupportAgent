# T5.3：Tool Execution → Business State 闭环

## 文件变更

- 新增 `application/context.py`：轻量 `AppContext`，只持有当前 `SupportSession`。
- 修改 `schemas/state.py`：新增持久事实 `warranty_status`、`ticket_id`。
- 修改 `tools/support_tools.py`：三个 SDK Tool 接入 Local Context，并拆出可测试的确定性业务函数。
- 修改 `workflow/stages.py`：权限函数接收完整 State；已有工单时移除 `create_ticket`。
- 修改 `application/turn_processor.py`：Main Agent Runner 传入 AppContext，Tool 执行后重算 Stage。
- 修改 `agents/support_agent.py`：State Context 增加 warranty status 和 ticket ID。
- 新增 `tests/test_tool_state_closure.py`，并适配原回归测试。
- 更新 `AGENTS.md` 和本报告。

## AppContext 与 ToolContext

`AppContext` 是 Agents SDK 的本地运行时依赖对象，仅包含 `session: SupportSession`。`process_turn` 使用：

```python
Runner.run_sync(agent, user_input, context=AppContext(session=session))
```

三个 Tool 的首个参数声明为 `ToolContext[AppContext]`，通过 `ctx.context.session.state` 获取同一个持久 State。SDK Local Context 不会自动进入 LLM Prompt，也没有复制或序列化整个 Session。

## Tool 状态效果

- `get_product` 调用 `find_product`：保留原返回值 `legacy demo product (removed)`，同时写入 `state.product`。
- `check_warranty` 调用 `find_warranty_status`：保留原 warranty 文本，同时写入 `state.warranty_status = "active"`。
- `create_ticket` 调用 `open_ticket`：首次写入固定 mock ID `A20260916001` 并保留原成功文本。

wrapper 只负责从 ToolContext 取 State 并调用确定性函数。Mock 外部业务未换成真实 API。

## 工单幂等与权限

采用两层程序保护：

1. `get_allowed_tools(state)` 在 diagnose 阶段检查 `state.ticket_id`；已有工单时不向 Agent 暴露 `create_ticket`。
2. `open_ticket` 自身再次检查 `ticket_id`。即使同一 Agent run 内模型重复调用、或代码绕过权限直接调用，也只返回已有 ID，不覆盖、不创建新工单。

Tool 执行完成后，`process_turn` 对同一个 State 再次执行 `next_stage`。产品查询可在本轮结束时把 Stage 从 `identify_product` 更新为 `understand_issue`；warranty 和 ticket 字段按现有 Stage 规则不会创造新阶段。

## 测试结果

运行 `.venv/bin/python -m unittest discover -s tests -v`：新增测试后共 21 项，全部通过。

覆盖内容：

- 使用真实 SDK `FunctionTool.on_invoke_tool` 和真实 `ToolContext[AppContext]` 验证三个 Tool 写入同一 Session State。
- 产品、保修和工单三个最小业务事实分别正确更新。
- 重复工单保持原 ID，业务函数不会再次创建，权限层也移除 Tool。
- Turn N 创建的 ticket 在 Turn N+1 保留、进入 Agent State Context，并影响 Tool Permission。
- Tool 执行前后 State identity 不变。
- 产品 Tool 执行后 Stage 重新计算为 `understand_issue`。
- 原 Text、Vision、RAG、Stage、next action、allowed tools、Session、History 及重资源生命周期测试继续通过。

## 未扩大处理的问题

- Tool 外部业务仍是 mock，没有真实售后数据库或订单 API。
- 没有外部调用失败事务回滚、Tool retry 或 Human approval。
- Tool 结果未单独复制到 conversation history；业务事实以 State 为准。
- 没有新增高级 RAG、Vision confidence/TTL、数据库持久化或 Web 前端。
- JSON parser robustness 保持现状。
- `warranty_status` 目前只有 mock 路径产生 `active`；未构建真实 expired/unknown 判定数据源。
