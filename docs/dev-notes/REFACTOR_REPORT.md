# 模块化重构记录

## 范围和结构

完整阅读原 main.py（约 700 行）、全部三份知识库后进行拆分。原项目没有自动测试、AGENTS.md、requirements.txt，也没有 Git 仓库。知识库及测试图片未修改。

```text
my_project/
├── __init__.py
├── main.py
├── AGENTS.md
├── requirements.txt
├── REFACTOR_REPORT.md
├── agents/
│   ├── __init__.py
│   ├── extractor_agent.py
│   └── support_agent.py
├── schemas/
│   ├── __init__.py
│   ├── state.py
│   └── vision.py
├── workflow/
│   ├── __init__.py
│   ├── stages.py
│   └── actions.py
├── tools/
│   ├── __init__.py
│   └── support_tools.py
├── rag/
│   ├── __init__.py
│   ├── loader.py
│   ├── embeddings.py
│   └── retriever.py
├── vision/
│   ├── __init__.py
│   ├── qwen.py
│   └── mock.py
├── providers/
│   ├── __init__.py
│   ├── deepseek.py
│   └── qwen.py
├── knowledge/
│   ├── legacy manual file (removed)
│   ├── legacy troubleshooting file (removed)
│   └── legacy manual file (removed)
├── test_images/
│   └── charging_contacts.png
└── tests/
    └── test_refactor.py
```

## 代码迁移与模块职责

| 文件 | 从原入口迁移的代码 |
|---|---|
| schemas/state.py | SupportState、StateUpdate，字段及默认值原样保留 |
| schemas/vision.py | VisionUpdate |
| workflow/stages.py | next_stage、apply_update、apply_vision_update；原 Tool 权限分支封装为 get_allowed_tools |
| workflow/actions.py | decide_next_action、can_create_ticket |
| tools/support_tools.py | get_product、check_warranty、create_ticket；保留装饰器、日志和固定返回值 |
| agents/extractor_agent.py | Extractor Prompt 与 Agent 组装；运行、JSON 解析、StateUpdate 构造和日志 |
| agents/support_agent.py | 原 state_context 和主 Agent Prompt、model/tools 组装 |
| rag/loader.py | KNOWLEDGE_DIR、load_knowledge_chunks；保留 Markdown 二级标题切块 |
| rag/embeddings.py | MiniLM 初始化、cosine_similarity |
| rag/retriever.py | tokenize、search_knowledge；原编码、排序、Top-K 和输出格式 |
| vision/qwen.py | image_to_data_url、analyze_image_qwen；原视觉 Prompt 和 JSON 解析 |
| vision/mock.py | analyze_image_mock |
| providers/deepseek.py | tracing 设置、AsyncOpenAI 客户端、deepseek-flash 模型封装 |
| providers/qwen.py | OpenAI 客户端、DashScope 地址和环境变量配置 |
| main.py | 示例输入、初始化、模块调用、原顺序和输出 |

## 行为说明

未修改业务规则、Prompt、模型提供商、模型名称、工具返回值、RAG 算法、State/Stage 权限。客户端、Agent、embedding 的模块级初始化改为入口调用的工厂；模型和视觉客户端通过参数传入业务模块。导入模块不再自动运行完整演示或发起服务调用，这是工程层面的启动行为变化。

资源路径按项目根目录定位；原图片相对路径改为绝对路径，因此图片分析日志中的路径相应变化。新增根 __init__.py 和入口导入路径处理，是为了区分项目 agents/ 与 SDK agents。requirements.txt 记录现有虚拟环境中的五项直接依赖版本，并非升级依赖。

真实原始执行顺序为：Extractor → StateUpdate → Vision → 合并 VisionUpdate → Next Action → 合并 StateUpdate → Stage → embedding/RAG → Context/Allowed Tools → 主 Agent。严格保留此顺序，没有借重构之机调整到需求所描述的理想顺序。

## 已发现、未修改的问题

1. 在文本状态合并之前计算 next_action，初始 issue 为 None，入口总是推荐 continue_diagnosis。这与所描述的理想链路不一致。
2. 动作规则仅检查 issue 中的字面量 `charge`；`charging` 或 `receiving power` 不匹配。Case 4 还需要 issue 满足该条件；仅两项视觉布尔值不足以触发清洁。
3. Mock Vision 的 indicator_on=True，但 observation 写着灯似乎关闭；保留原不一致。
4. can_create_ticket 未实际被调用；建单适宜性依赖主 Agent Prompt。工具返回结果不会反向更新 State，attempted_steps/resolved 也没有自动维护流程。
5. VisionUpdate.observation 仅打印，不合并进 SupportState 或主 Agent Context；主 Agent 接收现有视觉布尔字段。
6. RAG 每次加载知识并重复计算全部 chunk 的向量；保留无缓存、无阈值及原排序逻辑。原演示的额外 embedding encode 也保留。
7. 模型结果直接 json.loads，无 JSON 修复或业务层异常恢复；工具目前仍返回 mock 数据，输入仍为固定单轮示例。
8. 项目目录名与 Python 包名绑定；在父目录进行包导入，或使用 main.py 启动。直接把项目 agents 当顶层 SDK 使用会发生冲突。

## 验证结果与边界

- Python 编译检查通过。
- 新增 9 项 unittest 离线回归全部通过，覆盖状态合并、阶段、全部 Tool 权限、动作条件/优先级、图片编码和 VisionUpdate 合并、Mock Vision、检索排序/格式、Context 和模拟完整入口。
- Case 1：模拟 Extractor 返回后，user_name=Alice、stage=identify_product 通过。没有声称真实 DeepSeek 提取通过。
- Case 2：模拟提取后的 State/diagnose 通过；使用本地缓存的真实 all-MiniLM-L6-v2 检索 `legacy demo product (removed) won't charge`，Top-1 为故障排查“Device will not charge”（0.825），Top-2 为手册“Charging”（0.719）。
- Case 3：真实 PNG 的 Base64 请求构造、模拟 Qwen 返回的 VisionUpdate 验证及进入 State 通过。真实 Qwen 分析未完成。
- Case 4：issue="won't charge"、indicator_on=True、contacts_dirty=True 时，clean_charging_contacts 通过；原缺少 issue 的限制和动作优先级也通过。
- Case 5：验证传给主 Agent 的 instructions 包含 State、RAG、Vision、Workflow 和正确 Tool 列表；模拟最终输出通过。真实最终自然语言是否遵循这些信息尚未验证。
- 使用重构前源文件的临时快照进行 AST 对照与原/新程序模拟执行对照，核查原函数、Schema、Prompt、Agent 输入、权限和打印输出；仅允许图片绝对路径差异。快照保存在 /tmp/support-refactor-baseline，不是应用依赖。
- 从其他工作目录启动入口，导入可正常完成，但在创建 Qwen 客户端时因缺少 DASHSCOPE_API_KEY 停止。DEEPSEEK_API_KEY 同样未设置。

运行离线回归：`.venv/bin/python -m unittest discover -s tests -v`。

真实完整端到端验收仍未完成：需在运行环境提供两项 API Key，并能访问 DeepSeek 和 DashScope。配置后使用 `.venv/bin/python main.py` 执行保留的原始演示。本报告不把 mock 结果当作真实服务验收通过。
