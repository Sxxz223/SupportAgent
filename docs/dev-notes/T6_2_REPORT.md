# T6.2：React + TypeScript + Vite 文字客服前端

## 文件与结构

新增独立 `frontend/`：

```text
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts
│   │   └── client.test.ts
│   ├── components/
│   │   ├── ChatInput.tsx
│   │   ├── ChatWindow.tsx
│   │   └── MessageBubble.tsx
│   ├── test/setup.ts
│   ├── types/chat.ts
│   ├── App.test.tsx
│   ├── App.tsx
│   ├── main.tsx
│   ├── styles.css
│   └── vite-env.d.ts
├── .gitignore
├── index.html
├── package.json
├── package-lock.json
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
└── vite.config.ts
```

后端 API 契约和 Agent Core 未修改。`AGENTS.md` 增加前端职责和启动说明。

## 组件职责

- `App.tsx`：创建一次 Backend Session；维护 UI messages、stage、loading 和 error；调用 API client。
- `ChatWindow`：显示消息与 loading；每次消息或 loading 变化时滚动到底部。
- `MessageBubble`：渲染单条 User/Assistant Bubble。
- `ChatInput`：本地输入值、Send、Enter 发送、Shift+Enter 换行、空消息拦截。

`App` 使用 mount guard 防止 React StrictMode 重复初始化 Session，并使用同步 ref 防止状态重渲染前的重复提交。刷新页面会重建 React 应用并创建新 Session。

## API Client

`src/api/client.ts` 集中封装全部 fetch：

- `createSession()` → `POST http://127.0.0.1:8000/session` → session ID。
- `sendMessage(sessionId, message)` → `POST /chat` → reply/stage。

默认 base URL 可通过 `VITE_API_BASE_URL` 覆盖。非 2xx 会优先显示后端 `detail`，否则显示 HTTP status，不让异常导致页面崩溃。

## 状态边界

前端只保存 `sessionId`、用于显示的 `{id, role, content}` 消息、后端返回的 stage 标签和 UI 状态。SupportState、ticket、warranty、Workflow、Events 和 Agent Context 均继续由后端 SupportSession 管理。

用户消息立即显示并清空输入。请求期间输入和按钮禁用，显示 `Support is thinking…`；请求失败保留已发送 User Bubble并显示可读错误。Session 初始化失败提供 Retry connection。

## 验证

- Vitest：2 个测试文件、6 项测试全部通过。
- 覆盖 API URL/body、StrictMode 只创建一个 Session、两轮复用同一 ID、loading/disabled、错误提示、Shift+Enter 和空输入。
- Production build 成功：TypeScript 编译和 Vite bundle 均通过；JS 约 223 KB（gzip 约 70 KB），CSS 约 3.6 KB（gzip 约 1.4 KB）。
- 后端现有 34 项 Python 测试全部通过。
- 浏览器真实验证：`http://localhost:5173` 成功创建后端 Session并显示 Online；连续发送 `I'm Alice.`、`My product is legacy demo product (removed).`、供电问题，Stage 依次进入 identify_product、understand_issue、diagnose，并收到真实 Agent/RAG 回复。刷新后聊天清空并建立新 Session。
- 验证了后端 CORS 的精确行为：必须使用 `localhost:5173`；`127.0.0.1:5173` 不在允许 origin 中。

## 启动

后端（项目根目录）：

```bash
.venv/bin/uvicorn api.app:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173`。可用 `npm test` 和 `npm run build` 验证。

## 未扩大处理的问题

- 不渲染 Markdown，因此模型回复中的 Markdown 标记按纯文本显示。
- 没有图片上传、streaming、WebSocket、登录、多 Session UI 或前端持久化。
- 页面刷新会创建新后端 Session，旧内存 Session 由后端进程继续保留；当前后端没有 TTL/清理机制。
- 当前只显示后端 stage 作为轻量调试信息，不暴露完整 State。
- 前端未实现请求取消；页面卸载时正在执行的后端请求可能继续完成。
