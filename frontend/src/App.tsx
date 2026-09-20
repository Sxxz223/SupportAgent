import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createSession, getSessionEventsUrl, sendMessage, sendMultimodalMessage } from "./api/client";
import { ChatInput } from "./components/ChatInput";
import type { ChatResponse, FocusPath, Interaction, SolutionPlan, TaskStage, TaskUpdate, UiMessage } from "./types/chat";
import "./resolve/workspace.css";

const stageProgress: Record<TaskStage, number> = {
  confirmed: 10, collecting: 30, information_ready: 50, judgement_formed: 70,
  solution_provided: 90, waiting_confirmation: 99, completed: 100,
};
const presence = {
  thinking: ["🤔", "正在思考"], investigating: ["🔍", "正在排查"],
  insight: ["💡", "发现线索"], done_step: ["✅", "已有进展"], resolved: ["🎉", "问题已解决"],
} as const;
const initialFocus: FocusPath = {
  currentState: "等待你的问题", knownFacts: [], currentJudgement: "—", nextDirection: "—",
};
type Pending = { message: string; image: File | null };

export default function App() {
  const [sessionId, setSessionId] = useState("");
  const [tasks, setTasks] = useState<Record<string, TaskUpdate>>({});
  const [focusTaskId, setFocusTaskId] = useState("");
  const [focusPath, setFocusPath] = useState<FocusPath>(initialFocus);
  const [plan, setPlan] = useState<SolutionPlan>({ steps: [] });
  const [messages, setMessages] = useState<UiMessage[]>([
    { id: "welcome", role: "assistant", content: "你好，我是 Anker 智能服务助手。有什么可以帮你？" },
  ]);
  const [interaction, setInteraction] = useState<Interaction>({ type: "text" });
  const [agentState, setAgentState] = useState<keyof typeof presence | null>(null);
  const [visionResult, setVisionResult] = useState<ChatResponse["visionResult"]>();
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const requestVersion = useRef(0);
  const proactiveTimer = useRef<number | null>(null);
  const lastProactiveAt = useRef(0);
  const messageEnd = useRef<HTMLDivElement>(null);

  const taskList = useMemo(() => Object.values(tasks), [tasks]);
  const focusedTask = tasks[focusTaskId];
  const [presenceEmoji, presenceLabel] = agentState ? presence[agentState] : ["AI", "在线"];
  const canUpload = Boolean(interaction.image?.enabled || interaction.type === "partial_reshoot");

  const cancelProactive = useCallback(() => {
    if (proactiveTimer.current !== null) window.clearTimeout(proactiveTimer.current);
    proactiveTimer.current = null;
  }, []);

  const connect = useCallback(async () => {
    const version = ++requestVersion.current;
    setBusy(true); setError("");
    try {
      const id = await createSession();
      if (requestVersion.current === version) setSessionId(id);
    } catch {
      if (requestVersion.current === version) setError("暂时无法连接服务，请重试。");
    } finally {
      if (requestVersion.current === version) setBusy(false);
    }
  }, []);

  useEffect(() => { void connect(); return () => { requestVersion.current += 1; cancelProactive(); }; }, [connect, cancelProactive]);
  useEffect(() => { messageEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    if (!sessionId) return;
    const source = new EventSource(getSessionEventsUrl(sessionId));
    source.addEventListener("proactive_message", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { id?: string; content?: string; expiresInSeconds?: number };
      if (!data.content || Date.now() - lastProactiveAt.current < 8000) return;
      cancelProactive();
      proactiveTimer.current = window.setTimeout(() => {
        setMessages((current) => [...current, { id: data.id ?? crypto.randomUUID(), role: "proactive", content: data.content! }]);
        lastProactiveAt.current = Date.now();
      }, Math.min((data.expiresInSeconds ?? 2) * 500, 1800));
    });
    return () => source.close();
  }, [sessionId, cancelProactive]);

  function applyResponse(response: ChatResponse) {
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: response.reply }]);
    if (response.taskUpdates) {
      setTasks((current) => {
        const next = { ...current };
        response.taskUpdates!.forEach((task) => { next[task.taskId] = { ...next[task.taskId], ...task }; });
        return next;
      });
    }
    if (response.focusTaskId) setFocusTaskId(response.focusTaskId);
    if (response.focusPath) setFocusPath(response.focusPath);
    if (response.plan) setPlan(response.plan);
    setInteraction(response.interaction ?? { type: "text" });
    setAgentState(response.agentState?.emoji ?? null);
    setVisionResult(response.visionResult);
  }

  async function submit(message: string, image: File | null) {
    if (!sessionId) return;
    cancelProactive();
    setBusy(true); setError(""); setPending({ message, image });
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: message || "已上传图片" }]);
    setAgentState(image ? "investigating" : "thinking");
    try {
      const response = image
        ? await sendMultimodalMessage(sessionId, message, image, {
            taskId: focusTaskId, interactionType: interaction.type,
            target: interaction.image?.target, fields: interaction.image?.fields,
          })
        : await sendMessage(sessionId, message);
      applyResponse(response); setPending(null);
    } catch {
      setError("发送失败，内容已保留。");
    } finally { setBusy(false); }
  }

  function choose(id: string, label: string, value?: string) {
    cancelProactive();
    void submit(value ?? label, null);
  }

  function reset() {
    cancelProactive(); requestVersion.current += 1;
    setTasks({}); setFocusTaskId(""); setFocusPath(initialFocus);
    setPlan({ steps: [] });
    setMessages([{ id: "welcome", role: "assistant", content: "你好，我是 Anker 智能服务助手。有什么可以帮你？" }]);
    setInteraction({ type: "text" }); setAgentState(null); setVisionResult(undefined);
    setPending(null); setError(""); setSessionId(""); void connect();
  }

  return (
    <div className="service-app">
      <header className="service-header">
        <a className="service-brand" href="/" aria-label="Anker 智能服务首页"><b>A</b><span><strong>ANKER</strong><small>智能服务</small></span></a>
        <div><span className="service-online"><i />在线</span><button type="button" onClick={reset}>重新开始</button></div>
      </header>

      {taskList.length > 1 && <section className="task-bar" aria-label="服务任务">
        <div className="task-bar__inner">{taskList.map((task) => <article key={task.taskId}>
          <div><strong>{task.name}</strong><span>{stageProgress[task.stage]}%</span></div>
          <div className="task-meter"><i style={{ width: `${stageProgress[task.stage]}%` }} /></div>
          <p>{task.statusText}</p>
        </article>)}</div>
      </section>}

      <main className="service-workspace">
        <aside className="focus-panel" aria-label="当前解决重点">
          <p className="panel-kicker">实时解决路径</p>
          <h2>{focusedTask?.name ?? "等待开始"}</h2>
          {plan.steps.length > 0 && <ol className="solution-path" aria-label="解决步骤">
            {plan.steps.map((step) => <li key={step.id} className={`is-${step.status}`}>
              <i aria-hidden="true">{step.status === "done" ? "✓" : step.status === "current" ? "●" : ""}</i>
              <span>{step.title}</span>
            </li>)}
          </ol>}
          {plan.revision_note && <p className="path-revision">路径已更新：{plan.revision_note}</p>}
          <section><span>当前状态</span><p>{focusPath.currentState}</p></section>
          {focusPath.knownFacts.length > 0 && <section><span>已确认</span><ul>{focusPath.knownFacts.map((fact) => <li key={fact}>{fact}</li>)}</ul></section>}
          <section><span>当前判断</span><p>{focusPath.currentJudgement}</p></section>
          <section><span>后续方向</span><p>{focusPath.nextDirection}</p></section>
        </aside>

        <section className="conversation-card">
          <header className="agent-presence">
            <b className={agentState ? "is-active" : ""}>{presenceEmoji}</b>
            <span><strong>Anker 智能服务助手</strong><small>{presenceLabel}</small></span>
          </header>
          <div className="chat-stream" aria-live="polite">
            {messages.map((message) => <div key={message.id} className={`stream-message is-${message.role}`}>
              {message.role !== "user" && <b>{message.role === "proactive" ? "AI" : presenceEmoji}</b>}
              <p>{message.content}</p>
            </div>)}
            {busy && <div className="stream-thinking"><i /><i /><i /></div>}
            <div ref={messageEnd} />
          </div>

          <div className="action-panel" aria-label="当前操作">
            {interaction.question && <h3>{interaction.question}</h3>}
            {visionResult && <div className="vision-result">
              {visionResult.fields.map((field) => <div key={field.key} className={field.status === "unclear" ? "is-unclear" : ""}>
                <span>{field.label}</span><strong>{field.value ?? "需要补充"}</strong>
              </div>)}
            </div>}
            {(interaction.options?.length ?? 0) > 0 && <div className={`action-options is-${interaction.type}`}>
              {interaction.options!.map((option, index) => <button key={option.id ?? index} type="button" onClick={() => choose(option.id ?? `option-${index}`, option.label, option.value)} disabled={busy}>
                <span>{option.label}</span>{option.detail && <small>{option.detail}</small>}
              </button>)}
            </div>}
            {canUpload && <div className="image-guidance"><strong>{interaction.image?.label ?? "补拍图片"}</strong><p>{interaction.image?.target}</p></div>}
            {error && <div className="action-error" role="alert"><span>{error}</span><button type="button" onClick={() => pending && void submit(pending.message, pending.image)}>重试</button></div>}
            <ChatInput disabled={busy || !sessionId} onSend={submit} allowImages={canUpload} onInteract={cancelProactive} />
          </div>
        </section>
      </main>
    </div>
  );
}
