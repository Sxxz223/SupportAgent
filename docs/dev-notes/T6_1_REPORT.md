# T6.1：FastAPI API Layer

## 文件变更与结构

新增：

```text
api/
├── __init__.py
├── app.py
├── schemas.py
└── session_store.py
```

- `api/app.py`：FastAPI app factory、CORS 和三个 endpoint。
- `api/session_store.py`：进程内 Session Store。
- `api/schemas.py`：Health、Session、Chat 的 Pydantic HTTP schema。
- `tests/test_api.py`：HTTP 和多 Session 回归测试。
- `requirements.txt`：加入 FastAPI 0.141.1 和现有 Uvicorn 0.53.0。
- `AGENTS.md`：记录 API 职责和启动命令。

没有修改 Agent Core、Provider、RAG、Workflow、Tool、Context Builder 或 process_turn 的业务语义。CLI `main.py` 保留。

## Session Store

`InMemorySessionStore` 在每个 FastAPI app 实例中维护 `dict[str, SupportSession]`，使用 UUID4 字符串作为公开 ID。`create_session()` 创建全新的 SupportSession 并返回 ID；`get_session()` 只查询，找不到时返回 None，不隐式创建。映射访问使用轻量 `RLock`。

Store 挂载在 `app.state.session_store`，而不是把某个 SupportSession 作为所有用户共享的全局对象。`create_app()` 支持注入独立 Store 和 Turn Processor，便于测试及不同 app 实例隔离。

## Endpoint

- `GET /health`：返回 `{"status": "ok"}`。
- `POST /session`：创建并保存独立 Session，返回 `{"session_id": "<uuid>"}`。
- `POST /chat`：Pydantic 校验 session_id/message；查询既有 Session；调用 `process_turn(session=session, user_input=message, image_path=None)`；返回 `reply` 和当前 `stage`。不存在的 ID 返回 404 `Support session not found`，不会创建隐藏 Session。

响应不会返回完整 State、History、Events、Prompt、Model Context 或 Local Context。图片上传明确留待后续，因此 API 固定传入 `image_path=None`。

## 多 Session 与 CORS

不同 session_id 对应不同 SupportSession 和 SupportState 对象；同一 ID 的连续 `/chat` 请求复用同一对象。Store 数据仅存在于当前进程，重启或多 worker 之间不共享。

CORS 默认只允许 `http://localhost:5173`，允许 GET、POST、OPTIONS 和开发所需 headers/credentials；未配置全开放 origin。

## 验证

- 7 项 API 测试通过：health、UUID Session、chat 委托、多轮 State、404、不串 Session、CORS。
- 完整项目 34 项测试全部通过，原 Agent Core 回归保持正常。
- 使用真实命令 `.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8765` 启动成功；真实 HTTP `GET /health` 返回 200 和 `{"status":"ok"}`；验证后服务已关闭。
- API 测试以确定性 fake 替换 process_turn 边界，因此不依赖 API Key，也不声称真实 DeepSeek/Qwen 调用已在线验证。

## 启动

安装依赖：

```bash
.venv/bin/python -m pip install -r requirements.txt
```

从项目目录启动：

```bash
.venv/bin/uvicorn api.app:app --reload
```

## 未扩大处理的问题

- Store 不持久化，不跨进程或多 worker 共享；没有 Redis/数据库。
- 同一个 session_id 的并发 `/chat` 请求目前没有 turn 级串行锁，可能竞争修改同一个 Session。
- 未实现图片上传、WebSocket、streaming、认证、rate limit、production deployment 或 React 前端。
- Agent Provider 失败沿用 FastAPI 默认服务错误传播；未新增 retry、rollback 或外部错误分类协议。
- Session 没有 TTL、删除 endpoint 或容量回收策略。
