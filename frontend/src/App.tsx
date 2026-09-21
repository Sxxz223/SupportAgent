import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createSession, getSessionEventsUrl, reportActivity, resumeSession, sendMessage, sendMultimodalMessage } from "./api/client";
import { ChatInput } from "./components/ChatInput";
import type { AgentPresence, ChatResponse, FocusPath, Interaction, SolutionPlan, TaskStage, TaskUpdate, UiMessage } from "./types/chat";
import "./resolve/workspace.css";

const stageProgress: Record<TaskStage, number> = {
  confirmed: 10, collecting: 30, information_ready: 50, judgement_formed: 70,
  solution_provided: 90, waiting_confirmation: 99, completed: 100,
  cancelled: 0,
};
const defaultPresence: AgentPresence = { emoji: "🙂", label: "愿意听你说" };
const initialFocus: FocusPath = {
  currentState: "等待你的问题", knownFacts: [], currentJudgement: "—", nextDirection: "—",
};
const SESSION_STORAGE_KEY = "anker-support-session";
type Pending = { message: string; image: File | null };
function normalizeAgentState(state?: Partial<AgentPresence> | null): AgentPresence {
  if (!state?.emoji) return defaultPresence;
  const legacy: Record<string, AgentPresence> = {
    thinking: { emoji: "🤔", label: "认真听着" }, investigating: { emoji: "🧐", label: "陪你理清" },
    insight: { emoji: "😊", label: "有眉目了" }, done_step: { emoji: "🙌", label: "一起推进了" },
    resolved: { emoji: "🥳", label: "真替你开心" },
  };
  return legacy[state.emoji] ?? { emoji: state.emoji, label: state.label || "陪着你" };
}

export default function App() {
  const [sessionId, setSessionId] = useState("");
  const [tasks, setTasks] = useState<Record<string, TaskUpdate>>({});
  const [focusTaskId, setFocusTaskId] = useState("");
  const [focusPath, setFocusPath] = useState<FocusPath>(initialFocus);
  const [plan, setPlan] = useState<SolutionPlan>({ steps: [] });
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [interaction, setInteraction] = useState<Interaction>({ type: "text" });
  const [agentState, setAgentState] = useState<AgentPresence>(defaultPresence);
  const [visionResult, setVisionResult] = useState<ChatResponse["visionResult"]>();
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const requestVersion = useRef(0);
  const lastProactiveAt = useRef(0);
  const proactiveIds = useRef(new Set<string>());
  const acceptProactive = useRef(true);
  const caseVersion = useRef(0);
  const currentTurnId = useRef("");
  const messageEnd = useRef<HTMLDivElement>(null);
  const typingIdleTimer = useRef<number | undefined>(undefined);
  const typingActive = useRef(false);

  const taskList = useMemo(() => Object.values(tasks), [tasks]);
  const focusedTask = tasks[focusTaskId];
  const { emoji: presenceEmoji, label: presenceLabel } = agentState;
  const canUpload = Boolean(interaction.image?.enabled || interaction.type === "partial_reshoot");

  const cancelProactive = useCallback(() => {
    proactiveIds.current.clear();
    acceptProactive.current = false;
  }, []);

  const connect = useCallback(async () => {
    const version = ++requestVersion.current;
    setBusy(true); setError("");
    try {
      const storedId = window.localStorage.getItem(SESSION_STORAGE_KEY);
      if (storedId) {
        try {
          const restored = await resumeSession(storedId);
          if (requestVersion.current === version) {
            setSessionId(storedId);
            setMessages(restored.messages.length ? restored.messages.map((message) => ({
              ...message,
              agentState: message.role === "user" ? undefined : normalizeAgentState(message.agentState),
            })) : []);
            const restoredTasks: Record<string, TaskUpdate> = {};
            restored.taskUpdates?.forEach((task) => { restoredTasks[task.taskId] = task; });
            setTasks(restoredTasks); setFocusTaskId(restored.focusTaskId ?? "");
            setFocusPath(restored.focusPath ?? initialFocus); setPlan(restored.plan ?? { steps: [] });
            setInteraction(restored.interaction ?? { type: "text" });
            setAgentState(normalizeAgentState(restored.agentState));
            acceptProactive.current = true;
            caseVersion.current = restored.caseVersion ?? 0; currentTurnId.current = restored.turnId ?? "";
          }
          return;
        } catch { window.localStorage.removeItem(SESSION_STORAGE_KEY); }
      }
      const id = await createSession();
      if (requestVersion.current === version) {
        setSessionId(id); window.localStorage.setItem(SESSION_STORAGE_KEY, id);
      }
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
      const data = JSON.parse((event as MessageEvent).data) as { id?: string; content?: string; expiresInSeconds?: number; turnId?: string; caseVersion?: number; agentState?: AgentPresence };
      if (!acceptProactive.current || (data.caseVersion ?? 0) < caseVersion.current || (currentTurnId.current && data.turnId && data.turnId !== currentTurnId.current)) return;
      const id = data.id ?? crypto.randomUUID();
      if (!data.content || proactiveIds.current.has(id) || Date.now() - lastProactiveAt.current < 8000) return;
      proactiveIds.current.add(id);
      const messagePresence = normalizeAgentState(data.agentState ?? agentState);
      setMessages((current) => [...current, { id, role: "proactive", content: data.content!, agentState: messagePresence }]);
      lastProactiveAt.current = Date.now();
    });
    source.addEventListener("agent_state", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { emoji?: string; label?: string; turnId?: string; caseVersion?: number };
      const version = data.caseVersion ?? 0;
      if (version < caseVersion.current || version > caseVersion.current + 1) return;
      if (version === caseVersion.current && data.turnId && data.turnId !== currentTurnId.current) return;
      setAgentState(normalizeAgentState(data));
    });
    source.addEventListener("interaction_update", (event) => {
      const data = JSON.parse((event as MessageEvent).data) as { interaction?: Interaction; turnId?: string; caseVersion?: number };
      if (!acceptProactive.current || (data.caseVersion ?? 0) !== caseVersion.current || (data.turnId && data.turnId !== currentTurnId.current)) return;
      if (data.interaction) setInteraction(data.interaction);
    });
    return () => source.close();
  }, [sessionId, cancelProactive]);

  useEffect(() => {
    if (!sessionId) return;
    const reportFocus = () => {
      acceptProactive.current = true;
      void reportActivity(sessionId, "focus").catch(() => undefined);
    };
    const reportLeave = () => {
      cancelProactive();
      void reportActivity(sessionId, "leave").catch(() => undefined);
    };
    window.addEventListener("focus", reportFocus);
    window.addEventListener("blur", reportLeave);
    return () => {
      window.removeEventListener("focus", reportFocus);
      window.removeEventListener("blur", reportLeave);
    };
  }, [sessionId, cancelProactive]);

  function applyResponse(response: ChatResponse) {
    if (typeof response.caseVersion === "number" && response.caseVersion < caseVersion.current) return;
    if (typeof response.caseVersion === "number") caseVersion.current = response.caseVersion;
    if (response.turnId) currentTurnId.current = response.turnId;
    const responsePresence = normalizeAgentState(response.agentState);
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: response.reply, agentState: responsePresence }]);
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
    setAgentState(responsePresence);
    acceptProactive.current = true;
    setVisionResult(response.visionResult);
  }

  async function submit(message: string, image: File | null, displayMessage = message) {
    if (!sessionId) return;
    cancelProactive();
    setBusy(true); setError(""); setPending({ message, image });
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: displayMessage || "已上传图片" }]);
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
    void reportActivity(sessionId, "choice", id).catch(() => undefined);
    void submit(value ?? label, null, label);
  }

  const observeUser = useCallback((activity: "typing" | "image_selected") => {
    cancelProactive();
    if (!sessionId) return;
    if (activity === "typing") {
      if (!typingActive.current) {
        typingActive.current = true;
        void reportActivity(sessionId, "typing").catch(() => undefined);
      }
      window.clearTimeout(typingIdleTimer.current);
      typingIdleTimer.current = window.setTimeout(() => {
        typingActive.current = false;
        acceptProactive.current = true;
        void reportActivity(sessionId, "idle").catch(() => undefined);
      }, 1800);
    } else {
      void reportActivity(sessionId, activity).catch(() => undefined);
      acceptProactive.current = true;
    }
  }, [sessionId, cancelProactive]);

  function reset() {
    cancelProactive(); requestVersion.current += 1;
    setTasks({}); setFocusTaskId(""); setFocusPath(initialFocus);
    setPlan({ steps: [] });
    setMessages([]);
    setInteraction({ type: "text" }); setAgentState(defaultPresence); setVisionResult(undefined);
    setPending(null); setError(""); setSessionId("");
    caseVersion.current = 0; currentTurnId.current = "";
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    void connect();
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
            <b className="is-active">{presenceEmoji}</b>
            <span><strong>Anker 智能服务助手</strong><small>{presenceLabel}</small></span>
          </header>
          <div className="chat-stream" aria-live="polite">
            {messages.map((message) => <div key={message.id} className={`stream-message is-${message.role}`}>
              {message.role !== "user" && <b title={message.agentState?.label}>{message.agentState?.emoji ?? "🙂"}</b>}
              <p>{message.content}</p>
            </div>)}
            {busy && <div className="stream-thinking"><i /><i /><i /></div>}
            <div ref={messageEnd} />
          </div>

          <div className="action-panel" aria-label="当前操作">
            {interaction.question && <h3>{interaction.question}</h3>}
            {visionResult && <div className="vision-result">
              {visionResult.fields.map((field) => <div key={field.key} className={field.status === "unclear" ? "is-unclear" : ""}>
                <span>{field.label}</span><strong>{field.value == null ? "需要补充" : String(field.value)}</strong>
              </div>)}
            </div>}
            {(interaction.options?.length ?? 0) > 0 && <div className={`action-options is-${interaction.type}`}>
              {interaction.options!.map((option, index) => <button key={option.id ?? index} type="button" onClick={() => choose(option.id ?? `option-${index}`, option.label, option.value)} disabled={busy}>
                <span>{option.label}</span>{option.detail && <small>{option.detail}</small>}
              </button>)}
            </div>}
            {canUpload && <div className="image-guidance"><strong>{interaction.image?.label ?? "补拍图片"}</strong><p>{interaction.image?.target}</p></div>}
            {error && <div className="action-error" role="alert"><span>{error}</span><button type="button" onClick={() => pending && void submit(pending.message, pending.image)}>重试</button></div>}
            <ChatInput disabled={busy || !sessionId} onSend={submit} allowImages={canUpload} onInteract={observeUser} />
          </div>
        </section>
      </main>
    </div>
  );
}
