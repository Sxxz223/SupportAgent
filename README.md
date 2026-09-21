# SupportAgent

**面向安克黑客松智能服务赛道的 AI 客服 Agent 项目**

**An AI customer service agent project for the Anker Hackathon's intelligent service track**

[中文](#中文) · [English](#english)

## 中文

### 项目简介

SupportAgent 探索如何用 AI Agent 承接传统人工客服的核心工作：理解问题、确认信息、查找依据、指导排查、跟进结果，并在适当的时候结束处理或转交人工。

我们的出发点是一个可靠人工客服的工作流程。项目首先关注基础服务闭环能否稳定运行，再逐步探索多模态、动态排查路径、多任务处理和情绪感知等增强能力。

> **项目状态：** 当前为本地演示原型，已有多轮对话、规则工作流、产品知识检索、图片处理入口与演示业务工具。实现这些模块不等于已经稳定覆盖人工客服工作；真实模型效果仍需持续验证。本项目为黑客松参赛项目，不代表安克官方客服服务。

### 设计原则

- **先覆盖核心工作。** 优先完成一个范围明确、能够持续跟进的客服流程。
- **先保证可靠性。** 记住用户已提供的信息，跟踪已尝试的操作及结果，避免无意义的重复询问。
- **先决定下一步行动。** 根据当前案件状态选择追问、查询、排查、业务操作或结束处理，再组织回复。
- **让结论有依据。** 区分已确认事实、待确认信息与推测；缺少依据时继续确认或转交人工。
- **逐步扩展。** 先验证有限产品与问题场景，再增加知识、工具和交互方式。

### 核心服务流程

```text
用户描述问题
    ↓
理解信息并更新案件状态
    ↓
确认信息缺口 / 查询知识或业务信息
    ↓
选择下一步行动并给出明确指导
    ↓
获取用户反馈并更新判断
    ↓
继续排查 / 提供处理方案 / 转交人工
    ↓
确认处理结果并结束服务
```

这个流程需要支持多轮交互：每次反馈都应影响后续判断，问题得到解决前不能仅凭已给出建议就判定完成。

### 当前实现与边界

| 模块 | 仓库中的实现 | 当前边界 |
| --- | --- | --- |
| 多轮会话 | `SupportSession` 保存结构化状态、历史和运行记录。 | 会话保存在内存中，服务重启后丢失。 |
| 工作流 | Python 规则计算阶段、推荐动作与允许调用的工具。 | 当前排查规则有限，不代表通用动态诊断能力。 |
| 产品知识检索 | 按已确认产品过滤 Markdown 知识，使用 MiniLM 向量检索。 | 小规模知识库；未确认或不支持的产品不提供产品专属检索结果。 |
| 演示业务工具 | 客户核验、名下产品查询、保修查询与工单创建。 | 客户和订单使用本地 SQLite；工单为进程内演示实现，未对接真实售后系统。 |
| 图片辅助 | 图片经 Qwen 转为结构化视觉信息，再进入状态和上下文。 | 现有字段及部分规则仍偏向底座、触点等场景，不能视为覆盖目录内所有产品的视觉诊断。 |
| Web 界面 | FastAPI 后端，React / TypeScript / Vite 聊天与演示管理页面。 | 非流式回复；管理页面不具备生产级认证和权限控制。 |
| 评估与追踪 | 固定评估场景、逐轮 Trace、命令行和 JSON 报告。 | 离线测试不等于真实模型质量或线上服务可用性。 |

当前产品目录见 [`products/catalog.json`](products/catalog.json)：Anker Prime 250W（A2345）、Anker Nano 70W（A121A）、soundcore Liberty 4 NC（A3947）。目录条目不代表该产品的所有故障均已覆盖。

### 优先建设的核心能力

以下为开发目标，非已完成功能清单。

| 能力 | 目标 |
| --- | --- |
| 案件状态管理 | 保存产品、问题、已确认事实、已尝试操作及结果、当前阶段与处理状态。 |
| 信息提取与追问 | 从用户描述中整理有效信息，针对影响下一步判断的缺口进行追问。 |
| 下一步行动决策 | 根据已有信息，选择追问、指导测试、查询知识、调用业务工具、给出结论或确认结束。 |
| 知识支持 | 从范围有限、来源明确的产品资料与排查知识中获取依据。 |
| 业务工具衔接 | 探索产品信息、订单、保修与工单等操作；原型阶段可使用模拟数据与接口。 |
| 结果确认与人工转交 | 跟踪建议执行后的结果，识别尚未解决或超出能力范围的问题。 |

### 开发路线

1. **验证基础闭环：** 选择有限的产品与故障场景，验证信息收集、状态更新、排查指导和结果确认能否连续稳定运行。
2. **完善知识与工具：** 补充有来源的知识，明确模拟接口与真实接口的边界，验证异常情况及转人工流程。
3. **探索增强能力：** 在核心流程稳定后，再逐步评估图片等多模态输入、更复杂的动态排查路径、多任务处理与情绪感知。

增强能力属于后续探索方向，不应被理解为当前版本承诺。

### 评估关注点

- 用户已经提供的事实是否被保留和正确使用？
- 已完成的排查步骤是否被记录，是否避免不必要的重复？
- 下一步行动是否与当前信息和知识依据一致？
- 模拟业务结果是否与真实执行结果明确区分？
- 是否在获得反馈后才确认解决，并能在必要时转交人工？

### 本地运行

需要 Python、Node.js / npm，以及自己的 DeepSeek 和 DashScope API 密钥。以下命令在已克隆的仓库中执行，环境激活方式适用于 macOS / Linux。

```bash
cd SupportAgent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

如果已有 `.env`，保留现有文件。在 `.env` 中填写：

```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key
DASHSCOPE_API_KEY=your_dashscope_api_key
```

后端自动读取仓库根目录的 `.env`，已有环境变量优先；首次使用向量模型可能需要下载模型文件。

从仓库根目录启动后端：

```bash
.venv/bin/uvicorn api.app:app --reload
```

在另一个终端中，从仓库根目录启动前端：

```bash
cd frontend
npm install
npm run dev
```

- 聊天页面：[localhost:5173](http://localhost:5173)
- 演示管理页面：[localhost:5173/admin](http://localhost:5173/admin)
- API 文档：[127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

也可从仓库根目录运行命令行对话：`.venv/bin/python main.py`，输入 `exit` 退出。

### 测试与评估

从仓库根目录运行后端离线测试：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

前端检查：

```bash
cd frontend
npm test
npm run build
```

配置密钥后，可从仓库根目录运行真实模型评估（会调用外部 API，可能产生费用）：

```bash
.venv/bin/python -m evaluation.cli --all --json evaluation_results.json
```

`/debug/evaluation/latest` 和 `/debug/evaluation/summary` 读取已生成的报告，不会启动评估。本文不声明固定测试通过数量或模型准确率。

### 代码导航

| 目录 | 职责 |
| --- | --- |
| `application/`、`schemas/` | 会话、单轮编排及结构化状态。 |
| `support_agents/`、`context/`、`workflow/` | Agent 组装、上下文构建与确定性流程规则。 |
| `products/`、`knowledge/`、`rag/` | 产品目录、知识资料及检索。 |
| `tools/`、`services/`、`repositories/` | 工具调用、业务逻辑及数据存储。 |
| `providers/`、`vision/` | 模型提供方与图片理解。 |
| `api/`、`frontend/` | HTTP 接口与 Web 界面。 |
| `trace/`、`evaluation/`、`tests/` | 运行追踪、场景评估与回归测试。 |

### 已知限制

客户姓名配合手机尾号或订单号的核验仅服务于演示流程，不是生产级账户认证。API 与管理页面尚无生产级访问控制；当前系统适合本地演示。人工转接、复杂多任务处理和情绪感知尚不能作为已实现能力对外承诺。

### 参与协作

建议围绕范围明确的任务创建功能分支，通过 Pull Request 提交变更。提交说明应包含变更内容、验证方式及已知限制，并明确区分已实现功能、模拟行为和后续计划。

提交代码、演示数据或配置示例时，请勿包含 API 密钥、真实客户个人信息或未获授权的内部资料。

---

## English

### Overview

SupportAgent explores how an AI agent can handle the core work of a human customer service representative: understanding an issue, confirming details, finding supporting information, guiding troubleshooting, following up on results, and closing the case or handing it over to a human when appropriate.

We start with the workflow of a reliable human support representative. The first priority is a stable service loop. Multimodal input, dynamic troubleshooting paths, multitasking, and emotion awareness are directions for later exploration.

> **Project status:** This is a local demo prototype with multi-turn conversations, a rule-based workflow, product knowledge retrieval, an image-processing entry point, and demo business tools. Having these modules does not establish reliable coverage of human support work; live model behavior still needs ongoing validation. This is a hackathon entry, not an official Anker customer support service.

### Design Principles

- **Cover the core workflow first.** Start with a clearly scoped support process that can follow a case through multiple interactions.
- **Prioritize reliability.** Retain information already provided and track attempted steps and their results to avoid unnecessary repetition.
- **Decide the next action first.** Use the current case state to choose a question, lookup, troubleshooting step, business operation, or closure before composing a response.
- **Ground conclusions in evidence.** Distinguish confirmed facts, missing information, and hypotheses. Seek clarification or hand over to a human when evidence is insufficient.
- **Expand incrementally.** Validate a limited set of products and issues before adding knowledge, tools, and interaction modes.

### Core Service Flow

```text
User describes an issue
    ↓
Understand the information and update the case state
    ↓
Identify missing details / look up knowledge or business information
    ↓
Choose the next action and provide clear guidance
    ↓
Collect feedback and update the assessment
    ↓
Continue troubleshooting / offer a resolution / hand over to a human
    ↓
Confirm the outcome and close the case
```

This flow must support multiple turns: each response should inform the next decision. Giving advice alone is not enough to mark an issue as resolved.

### Current Implementation and Scope

| Module | Repository implementation | Current boundary |
| --- | --- | --- |
| Multi-turn sessions | `SupportSession` holds structured state, history, and runtime records. | Sessions are in memory and are lost on restart. |
| Workflow | Python rules determine stages, recommended actions, and permitted tools. | Troubleshooting rules are limited, not a general dynamic diagnosis system. |
| Product knowledge retrieval | Filters Markdown knowledge by confirmed product, then retrieves with MiniLM embeddings. | Small knowledge base; unknown or unsupported products receive no product-specific results. |
| Demo business tools | Customer verification, owned-product lookup, warranty lookup, and ticket creation. | Customers and orders use local SQLite; tickets are in-process demo records, with no real support-system integration. |
| Image assistance | Qwen converts images into structured observations used in state and context. | Existing fields and some rules still focus on docks and charging contacts; this does not establish visual diagnosis coverage for every catalog product. |
| Web interface | FastAPI backend with React / TypeScript / Vite chat and demo administration pages. | Non-streaming responses; administration has no production-grade authentication or access control. |
| Evaluation and tracing | Fixed scenarios, per-turn traces, CLI execution, and JSON reports. | Offline tests do not establish live model quality or service availability. |

The current [`products/catalog.json`](products/catalog.json) includes Anker Prime 250W (A2345), Anker Nano 70W (A121A), and soundcore Liberty 4 NC (A3947). A catalog entry does not imply coverage of every failure mode for that product.

### Core Development Priorities

The following are development goals, not a list of completed features.

| Capability | Goal |
| --- | --- |
| Case state management | Track the product, issue, confirmed facts, attempted steps and results, current stage, and resolution status. |
| Information extraction and clarification | Organize useful details from user messages and ask about gaps that affect the next decision. |
| Next-action decisions | Choose whether to ask a question, guide a test, search knowledge, call a business tool, provide a conclusion, or confirm closure. |
| Knowledge support | Retrieve evidence from a limited set of product references and troubleshooting guidance with clear sources. |
| Business tool integration | Explore product, order, warranty, and ticket operations; prototypes may use mock data and interfaces. |
| Outcome confirmation and human handoff | Follow up on the results of advice and identify unresolved issues or cases beyond the agent's capabilities. |

### Roadmap

1. **Validate the basic service loop:** Select a limited set of products and failure scenarios, then assess whether information collection, state updates, troubleshooting guidance, and outcome confirmation remain stable over multiple turns.
2. **Improve knowledge and tools:** Add sourced knowledge, clarify the boundary between mock and real integrations, and validate error handling and human handoff.
3. **Explore enhancements:** Once the core workflow is stable, evaluate multimodal inputs such as images, more complex dynamic troubleshooting paths, multitasking, and emotion awareness.

These enhancements are future exploration areas, not commitments for the current version.

### Evaluation Focus

- Are facts already provided by the user retained and used correctly?
- Are completed troubleshooting steps recorded, with unnecessary repetition avoided?
- Is the next action consistent with the available information and supporting knowledge?
- Are simulated business results clearly distinguished from real execution results?
- Is resolution confirmed only after feedback, with human handoff available when needed?

### Running Locally

You need Python, Node.js / npm, and your own DeepSeek and DashScope API keys. Run the following in your cloned repository; environment activation below is for macOS / Linux.

```bash
cd SupportAgent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Keep your existing `.env` if one is already present. Set the following values in that file:

```dotenv
DEEPSEEK_API_KEY=your_deepseek_api_key
DASHSCOPE_API_KEY=your_dashscope_api_key
```

The backend loads `.env` from the repository root; existing environment variables take precedence. First use of the embedding model may require a model download.

Start the backend from the repository root:

```bash
.venv/bin/uvicorn api.app:app --reload
```

In another terminal, start the frontend from the repository root:

```bash
cd frontend
npm install
npm run dev
```

- Chat: [localhost:5173](http://localhost:5173)
- Demo administration: [localhost:5173/admin](http://localhost:5173/admin)
- API documentation: [127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Alternatively, run `.venv/bin/python main.py` from the repository root for CLI chat. Enter `exit` to quit.

### Tests and Evaluation

Run backend offline tests from the repository root:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Frontend checks:

```bash
cd frontend
npm test
npm run build
```

After configuring credentials, run live model evaluation from the repository root (this calls external APIs and may incur charges):

```bash
.venv/bin/python -m evaluation.cli --all --json evaluation_results.json
```

`/debug/evaluation/latest` and `/debug/evaluation/summary` read existing reports; they do not run evaluations. This README makes no claim about a fixed passing test count or model accuracy.

### Code Navigation

| Directory | Responsibility |
| --- | --- |
| `application/`, `schemas/` | Sessions, turn orchestration, and structured state. |
| `support_agents/`, `context/`, `workflow/` | Agent assembly, context construction, and deterministic workflow rules. |
| `products/`, `knowledge/`, `rag/` | Product catalog, knowledge sources, and retrieval. |
| `tools/`, `services/`, `repositories/` | Tool calls, business logic, and persistence. |
| `providers/`, `vision/` | Model providers and image perception. |
| `api/`, `frontend/` | HTTP endpoints and web interfaces. |
| `trace/`, `evaluation/`, `tests/` | Runtime tracing, scenario evaluation, and regression tests. |

### Known Limitations

Matching a customer name with a phone suffix or order number supports the demo workflow; it is not production-grade account authentication. The API and administration interface lack production-grade access control and are intended for local demonstration. Human handoff, complex multitasking, and emotion awareness should not be presented as implemented capabilities.

### Contributing

We recommend working on focused tasks in feature branches and submitting changes through Pull Requests. Describe what changed, how it was validated, and any known limitations. Clearly distinguish implemented features, simulated behavior, and future plans.

Do not include API keys, real customer personal information, or unauthorized internal materials in code, demo data, or configuration examples.
