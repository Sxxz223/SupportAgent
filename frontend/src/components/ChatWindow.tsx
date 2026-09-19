import { useEffect, useRef } from "react";

import type { ChatMessage } from "../types/chat";
import { MessageBubble } from "./MessageBubble";

type ChatWindowProps = {
  messages: ChatMessage[];
  isThinking: boolean;
};

export function ChatWindow({ messages, isThinking }: ChatWindowProps) {
  const endRef = useRef<HTMLDivElement>(null);

  function scrollToLatest() {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  useEffect(() => {
    scrollToLatest();
  }, [messages, isThinking]);

  return (
    <section className="chat-window" aria-live="polite" aria-label="Conversation">
      <div className="message-column">
        {messages.length === 0 && (
          <div className="empty-state">
            <h2>How can we help?</h2>
            <p>Describe your product and what is happening.</p>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} onImageLoad={scrollToLatest} />
        ))}

        {isThinking && (
          <div className="typing-status" role="status" aria-label="Support is thinking">
            <span>Thinking</span>
            <span className="typing-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          </div>
        )}
        <div ref={endRef} />
      </div>
    </section>
  );
}
