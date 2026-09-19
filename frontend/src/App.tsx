import { useCallback, useEffect, useRef, useState } from "react";

import { createSession, sendMessage, sendMultimodalMessage } from "./api/client";
import { ChatInput } from "./components/ChatInput";
import { ChatWindow } from "./components/ChatWindow";
import GradientWavesBackground from "./components/GradientWavesBackground";
import type { ChatMessage } from "./types/chat";

const DEBUG = false;

function messageId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function reportAndFormatError(reason: unknown) {
  if (import.meta.env.DEV) console.error("Support request failed:", reason);
  return "We couldn't reach support. Please try again in a moment.";
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [stage, setStage] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionStartedRef = useRef(false);
  const requestInFlightRef = useRef(false);
  const messageImageUrlsRef = useRef(new Set<string>());

  const initializeSession = useCallback(async () => {
    setIsInitializing(true);
    setError(null);
    try {
      setSessionId(await createSession());
    } catch (reason) {
      setError(reportAndFormatError(reason));
    } finally {
      setIsInitializing(false);
    }
  }, []);

  useEffect(() => {
    if (sessionStartedRef.current) return;
    sessionStartedRef.current = true;
    void initializeSession();
  }, [initializeSession]);

  useEffect(() => () => {
    messageImageUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    messageImageUrlsRef.current.clear();
  }, []);

  const handleSend = useCallback(
    async (content: string, image: File | null) => {
      if (!sessionId || requestInFlightRef.current) return;

      requestInFlightRef.current = true;
      const imageUrl = image ? URL.createObjectURL(image) : undefined;
      if (imageUrl) messageImageUrlsRef.current.add(imageUrl);
      setMessages((current) => [
        ...current,
        { id: messageId(), role: "user", content, imageUrl },
      ]);
      setError(null);
      setIsThinking(true);

      try {
        const response = image
          ? await sendMultimodalMessage(sessionId, content, image)
          : await sendMessage(sessionId, content);
        setMessages((current) => [
          ...current,
          { id: messageId(), role: "assistant", content: response.reply },
        ]);
        setStage(response.stage);
      } catch (reason) {
        setError(reportAndFormatError(reason));
      } finally {
        requestInFlightRef.current = false;
        setIsThinking(false);
      }
    },
    [sessionId],
  );

  const inputDisabled = isInitializing || isThinking || sessionId === null;
  const connectionState = isInitializing ? "connecting" : sessionId ? "online" : "offline";

  return (
    <main className="app-shell">
      <div className="chat-background" aria-hidden="true">
        <GradientWavesBackground status={isThinking ? "thinking" : "idle"} />
      </div>
      <section className="chat-workspace" aria-label="Customer support chat">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Customer care</p>
            <h1>AI Support Assistant</h1>
          </div>
          <span className={`session-status session-status--${connectionState}`}>
            {isInitializing ? "Connecting" : sessionId ? "Online" : "Offline"}
          </span>
        </header>

        <ChatWindow messages={messages} isThinking={isThinking} />

        {DEBUG && stage && <p className="stage-label">Current stage: {stage}</p>}
        <div className="composer-layer">
          {error && (
            <div className="error-message" role="alert">
              <span>{error}</span>
              {!sessionId && (
                <button type="button" onClick={() => void initializeSession()}>
                  Retry connection
                </button>
              )}
            </div>
          )}
          <ChatInput
            disabled={inputDisabled}
            onSend={(message, image) => void handleSend(message, image)}
          />
        </div>
      </section>
    </main>
  );
}
