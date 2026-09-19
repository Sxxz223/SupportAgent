# T5.1：统一单轮交互编排

## 文件变更

- 新增 `application/__init__.py`：应用层包。
- 新增 `application/turn_processor.py`：统一同步入口 `process_turn(state, user_input, image_path=None) -> str`。
- 修改 `main.py`：保留 SDK 同名包导入处理；业务入口仅创建 State、准备本次指定文本和原测试图片、调用 process_turn、打印最终回复。
- 修改 `tests/test_refactor.py`：原入口集成测试的 mock 目标迁移到 application 层，保留原断言。
- 新增 `tests/test_turn_processor.py`：6 项编排回归测试。
- 修改 `AGENTS.md`：更新模块职责，撤销已被用户后续授权修改取代的历史顺序约束。
- 新增本报告；`REFACTOR_REPORT.md` 保留为首次拆分的历史记录。

## 接口与完整执行顺序

调用者传入的 SupportState 被原地更新；返回值为现有 Runner 的 final_output。无需由调用者创建模型或了解内部编排。

1. 通过现有工厂创建 DeepSeek model 和 Extractor Agent。
2. Extractor 处理 user_input，生成 StateUpdate。
3. apply_update 合并到传入的 State。
4. image_path 非空时，通过现有 Qwen 客户端工厂及 Vision 模块生成 VisionUpdate，再 apply_vision_update 合并。
5. next_stage 根据完整 State 更新 state.stage。
6. 保留 diagnose 门控：仅此阶段创建原 embedding 模型并执行原 search_knowledge；其他阶段知识上下文为空。
7. decide_next_action 根据完整 State 计算动作。
8. get_allowed_tools 根据 Stage 获取 Tool 对象和名称。
9. create_support_agent 使用原 Context/Prompt，传入 State、检索知识、动作、模型和允许工具；Vision 字段通过 State 进入 Context。
10. Runner.run_sync 运行主 Agent，返回 final_output。

无图片时跳过 Qwen 创建和分析，不清空已有视觉事实。空字符串也视为无图片。异常继续由原模块抛出，没有新增异常吞掉、回滚、重试或降级逻辑。该入口为同步调用，延续 Runner.run_sync，不新增异步接口。

## 行为与接口调整

没有修改 schemas、workflow、rag、vision、agents、tools、providers 中的任何实现或现有接口。模型、Prompt、工具权限、Stage 语义、RAG 算法和 Vision 算法保持不变。

按本任务明确要求调整编排：文本先合并，再分析及合并图片，然后 Stage → RAG → next_action → Tool Permission → Main Agent。保留前一轮已授权的三个修复。

删除入口中未被使用的演示向量 `encode("legacy demo product (removed) won't charge")`；embedding 初始化移到 diagnose 检索分支。它不参与原 RAG 输出，删除不改变检索算法或业务结果；减少非诊断轮次的无关初始化。Qwen 客户端只在有图片时创建，使无图片轮次不依赖 DashScope Key。原中间诊断日志迁移至应用层，顺序随编排要求调整；最终回复由 main 打印。

## 测试

运行 `.venv/bin/python -m unittest discover -s tests -v`：15 项全部通过（原 9 项 + 新 6 项）。

新增覆盖：

- 有图片时精确验证调用顺序；在 Stage 和动作计算处检查文本及新视觉事实已经合并，并验证覆盖旧视觉状态。
- 无图片时完整执行，断言不创建/调用 Qwen。
- 传入已有 State 时保留文本及视觉事实；空图片路径按无图片处理。
- 非 diagnose 阶段跳过 RAG，验证 identify_product 的 Tool 权限。
- 使用真实 PNG、真实 Extractor JSON 解析及真实 Vision 请求构造/解析，模拟外部服务响应，贯通 State、主 Agent 和最终返回。
- main 仅委托 process_turn 并打印返回值。

另以题目给定文本和原真实 PNG 运行 process_turn，保留本地缓存的真实 all-MiniLM-L6-v2 及 RAG，只模拟 DeepSeek/Qwen 服务响应。验证充电知识进入 Agent Context、State=Alice/legacy demo product (removed)、Stage=diagnose、视觉事实已合并、next_action=clean_charging_contacts、允许工具为 check_warranty/create_ticket。

当前环境两项 API Key 均未设置。因此真实 DeepSeek 提取质量、Qwen 图片感知及最终自然语言回复未完成线上验收。模拟测试验证传给主 Agent 的 State/RAG/Vision/Workflow 信息完整，不声称真实最终回答必然遵循。

## 发现但未修改的问题

- 每轮创建模型/客户端；diagnose 轮次重新加载 embedding。未引入缓存、会话管理或生命周期改造。
- 图片分析或后续服务失败时，先前已合并的 State 不回滚；未添加新的事务语义。
- 无图片轮次保留历史视觉事实，未增加事实过期规则。
- Vision observation 仍只打印，Agent 使用现有视觉布尔字段。
- Tool 仍为原 mock 业务能力，结果不自动回写 State；未增加工具反馈闭环。
- 既有模型 JSON 解析和充电关键词规则保持原样，未扩展成新的容错或语义分类方案。
