import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createSession, sendMessage, sendMultimodalMessage } from "./api/client";
import { ChatInput } from "./components/ChatInput";
import { advanceDemo, demoView, initialDemo } from "./resolve/demo";
import { liveView } from "./resolve/model";
import "./resolve/workspace.css";

type PendingMessage = { message: string; image: File | null };

export default function App() {
  const isDemo = window.location.pathname === "/demo";
  const [sessionId, setSessionId] = useState("");
  const [stage, setStage] = useState("identify_user");
  const [reply, setReply] = useState("你好，我是 Anker 智能服务助手。我们一步一步来解决问题。");
  const [demo, setDemo] = useState(initialDemo);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(!isDemo);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<PendingMessage | null>(null);
  const requestVersion = useRef(0);

  const view = useMemo(
    () => (isDemo ? demoView(demo) : liveView(stage, confirmed)),
    [isDemo, demo, stage, confirmed],
  );

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
      setStage(response.stage);
      if (response.stage === "resolved" && /确认.*解决|问题.*解决/.test(message)) setConfirmed(true);
      setPending(null);
    } catch {
      setError("发送失败，内容已保留。你可以直接重试。");
    } finally {
      setBusy(false);
    }
  }

  function handleSend(message: string, image: File | null) {
    if (isDemo) {
      if (message.trim()) setReply("已收到你的补充。请选择最接近的结果，我们会继续调整解决步骤。");
      return;
    }
    void submitLive(message, image);
  }

  function choose(choice: (typeof view.choices)[number]) {
    if (isDemo) {
      setDemo((current) => advanceDemo(current, choice.id));
      return;
    }
    void submitLive(choice.message ?? choice.label, null);
  }

  function reset() {
    requestVersion.current += 1;
    setStage("identify_user");
    setReply("你好，我是 Anker 智能服务助手。我们一步一步来解决问题。");
    setDemo(initialDemo());
    setConfirmed(false);
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
          <h1>你好，需要我帮你解决什么问题？</h1>
        </section>

        <div className="resolve-layout">
          <aside className="resolve-progress" aria-label="解决进度">
            <div className="resolve-progress-title">
              <h2>解决进度</h2>
              {view.progress !== null && <span>{view.progress}%</span>}
            </div>
            {view.progress !== null && <div className="resolve-progress-bar"><i style={{ width: `${view.progress}%` }} /></div>}
            <ol>
              {view.steps.map((step) => (
                <li key={step.id} className={`resolve-step is-${step.status}`} aria-current={step.status === "current" ? "step" : undefined}>
                  <span>{step.status === "done" ? "✓" : ""}</span>
                  <p>{step.title}</p>
                </li>
              ))}
            </ol>
          </aside>

          <section className="resolve-card" aria-live="polite">
            <div className="resolve-assistant">
              <span>AI</span>
              <div><strong>Anker 智能服务助手</strong><small>正在为你解决问题</small></div>
            </div>

            <div className="resolve-content">
              {view.note && <div className="resolve-note">路径已更新 · {view.note}</div>}
              <p className="resolve-eyebrow">{view.eyebrow}</p>
              <h2>{view.title}</h2>
              <p className="resolve-description">{view.description}</p>

              {view.progress !== null && view.progress >= 99 && (
                <div className={`resolve-score ${view.complete ? "is-complete" : ""}`}>
                  <strong>{view.progress}</strong><span>%</span>
                  <p>{view.complete ? "问题已解决" : "等待你的最终确认"}</p>
                </div>
              )}

              {!view.complete && reply && (
                <div className="resolve-reply"><span>AI</span><p>{reply}</p></div>
              )}

              {error && (
                <div className="resolve-error" role="alert">
                  <span>{error}</span>
                  <button type="button" onClick={() => pending ? void submitLive(pending.message, pending.image) : void connect()}>重试</button>
                </div>
              )}

              {!view.complete && view.choices.length > 0 && (
                <div className="resolve-choices">
                  {view.choices.map((choice) => (
                    <button key={choice.id} type="button" onClick={() => choose(choice)} disabled={busy}>
                      <span>{choice.label}</span>{choice.detail && <small>{choice.detail}</small>}
                      <i>›</i>
                    </button>
                  ))}
                </div>
              )}

              {view.complete ? (
                <button className="resolve-primary" type="button" onClick={reset}>解决下一个问题</button>
              ) : (
                <div className="resolve-composer">
                  <ChatInput disabled={busy || (!isDemo && !sessionId)} onSend={handleSend} allowImages={!isDemo} />
                  <p>你可以选择上方选项，也可以直接描述情况</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
