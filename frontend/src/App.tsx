import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createSession, sendMessage, sendMultimodalMessage } from "./api/client";
import { ChatInput } from "./components/ChatInput";
import { advanceDemo, demoView, initialDemo } from "./resolve/demo";
import type { ChatResponse } from "./types/chat";
import "./resolve/workspace.css";

type PendingMessage = { message: string; image: File | null };

export default function App() {
  const isDemo = window.location.pathname === "/demo";
  const [sessionId, setSessionId] = useState("");
  const [reply, setReply] = useState("你好，我是 Anker 智能服务助手。有什么可以帮你？");
  const [lastUserMessage, setLastUserMessage] = useState("");
  const [agentResult, setAgentResult] = useState<ChatResponse | null>(null);
  const [started, setStarted] = useState(false);
  const [demo, setDemo] = useState(initialDemo);
  const [busy, setBusy] = useState(!isDemo);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<PendingMessage | null>(null);
  const requestVersion = useRef(0);

  const demoResult = useMemo(() => demoView(demo), [demo]);
  const steps = isDemo ? (started ? demoResult.steps : []) : (agentResult?.plan?.steps ?? []);
  const progress = isDemo ? (started ? demoResult.progress : null) : (agentResult?.plan?.progress ?? null);
  const complete = isDemo ? demoResult.complete : progress === 100;
  const choices = isDemo ? (started ? demoResult.choices : []) : (agentResult?.interaction?.options ?? []).map((option, index) => ({
    id: option.id ?? `option-${index}`, label: option.label, detail: option.detail, message: option.value ?? option.label,
  }));
  const title = !started ? "有什么可以帮你？" : isDemo ? demoResult.title : steps.find((step) => step.status === "current")?.title ?? "继续处理";
  const description = !started ? "" : isDemo ? demoResult.description : "";
  const note = isDemo ? demoResult.note : agentResult?.plan?.revision_note;
  const allowImages = !isDemo && agentResult?.interaction?.type === "image";

  const connect = useCallback(async () => {
    const version = ++requestVersion.current;
    setBusy(true);
    setError("");
    try {
      const id = await createSession();
      if (requestVersion.current === version) setSessionId(id);
    } catch {
      if (requestVersion.current === version) setError("暂时无法开始服务，请稍后重试。");
    } finally {
      if (requestVersion.current === version) setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!isDemo) void connect();
    return () => { requestVersion.current += 1; };
  }, [connect, isDemo]);

  async function submitLive(message: string, image: File | null) {
    if (!sessionId) return;
    setBusy(true);
    setError("");
    setPending({ message, image });
    try {
      const response = image
        ? await sendMultimodalMessage(sessionId, message, image)
        : await sendMessage(sessionId, message);
      setReply(response.reply);
      setAgentResult(response);
      setStarted(true);
      setPending(null);
    } catch {
      setError("发送失败，内容已保留。你可以直接重试。");
    } finally {
      setBusy(false);
    }
  }

  function handleSend(message: string, image: File | null) {
    setLastUserMessage(message || "已上传图片");
    if (isDemo) {
      if (!started) {
        setStarted(true);
        setReply("明白了。我先确认产品和现象，再根据你的反馈生成后续步骤。");
      } else if (message.trim()) setReply("已收到你的补充。我会根据新情况调整接下来的步骤。");
      return;
    }
    void submitLive(message, image);
  }

  function choose(choice: (typeof choices)[number]) {
    setLastUserMessage(choice.label);
    if (isDemo) {
      setDemo((current) => advanceDemo(current, choice.id));
      return;
    }
    void submitLive(choice.message ?? choice.label, null);
  }

  function reset() {
    requestVersion.current += 1;
    setReply("你好，我是 Anker 智能服务助手。有什么可以帮你？");
    setLastUserMessage("");
    setAgentResult(null);
    setStarted(false);
    setDemo(initialDemo());
    setError("");
    setPending(null);
    setSessionId("");
    if (!isDemo) void connect();
  }

  return (
    <div className="resolve-app">
      <header className="resolve-header">
        <a className="resolve-brand" href={isDemo ? "/demo" : "/"} aria-label="Anker Resolve 首页">
          <span className="resolve-mark">A</span>
          <span><strong>ANKER</strong><small>Resolve</small></span>
        </a>
        <div className="resolve-header-actions">
          <span className="resolve-online"><i />在线服务</span>
          <button type="button" className="resolve-reset" onClick={reset}>重新开始</button>
        </div>
      </header>

      <main className="resolve-main">
        <section className="resolve-intro">
          <p>ANKER 智能服务</p>
          <h1>智能服务</h1>
        </section>

        <div className="resolve-layout">
          <aside className="resolve-progress" aria-label="解决路径">
            <div className="resolve-progress-title">
              <h2>解决路径</h2>
              {progress !== null && <span>{progress}%</span>}
            </div>
            {progress !== null && <div className="resolve-progress-bar"><i style={{ width: `${progress}%` }} /></div>}
            {steps.length > 0 ? <ol>
              {steps.map((step) => (
                <li key={step.id} className={`resolve-step is-${step.status}`} aria-current={step.status === "current" ? "step" : undefined}>
                  <span>{step.status === "done" ? "✓" : ""}</span>
                  <p>{step.title}</p>
                </li>
              ))}
            </ol> : <div className="resolve-path-placeholder" aria-label="路径将在分析后显示">
              <i /><i /><i /><i />
            </div>}
          </aside>

          <section className="resolve-card" aria-live="polite">
            <div className="resolve-assistant">
              <span>AI</span>
              <div><strong>Anker 智能服务助手</strong><small>在线</small></div>
            </div>

            <div className="resolve-content">
              {note && <div className="resolve-note">接下来的步骤已调整 · {note}</div>}
              {started && <p className="resolve-eyebrow">当前步骤</p>}
              <h2>{title}</h2>
              {description && <p className="resolve-description">{description}</p>}

              {progress !== null && progress >= 99 && (
                <div className={`resolve-score ${complete ? "is-complete" : ""}`}>
                  <strong>{progress}</strong><span>%</span>
                  <p>{complete ? "问题已解决" : "等待你的最终确认"}</p>
                </div>
              )}

              {lastUserMessage && <div className="resolve-user-message"><p>{lastUserMessage}</p></div>}
              {!complete && reply && (
                <div className="resolve-reply"><span>AI</span><p>{reply}</p></div>
              )}

              {error && (
                <div className="resolve-error" role="alert">
                  <span>{error}</span>
                  <button type="button" onClick={() => pending ? void submitLive(pending.message, pending.image) : void connect()}>重试</button>
                </div>
              )}

              {!complete && choices.length > 0 && (
                <div className="resolve-choices">
                  {choices.map((choice) => (
                    <button key={choice.id} type="button" onClick={() => choose(choice)} disabled={busy}>
                      <span>{choice.label}</span>{choice.detail && <small>{choice.detail}</small>}
                      <i>›</i>
                    </button>
                  ))}
                </div>
              )}

              {complete ? (
                <button className="resolve-primary" type="button" onClick={reset}>解决下一个问题</button>
              ) : (
                <div className="resolve-composer">
                  {allowImages && agentResult?.interaction?.image_prompt && <p className="resolve-image-prompt">{agentResult.interaction.image_prompt}</p>}
                  <ChatInput disabled={busy || (!isDemo && !sessionId)} onSend={handleSend} allowImages={allowImages} />
                  {choices.length > 0 && <p>也可以补充实际情况</p>}
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
