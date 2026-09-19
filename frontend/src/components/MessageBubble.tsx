import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";

import type { ChatMessage } from "../types/chat";

type MessageBubbleProps = {
  message: ChatMessage;
  onImageLoad?: () => void;
};

export function MessageBubble({ message, onImageLoad }: MessageBubbleProps) {
  const label = message.role === "user" ? "You" : "Support";

  return (
    <article className={`message message--${message.role}`}>
      <span className="message__label">{label}</span>
      <div className="message__body">
        {message.imageUrl && (
          <img
            className="message__image"
            src={message.imageUrl}
            alt="Uploaded attachment"
            onLoad={onImageLoad}
          />
        )}
        {message.content && (
          message.role === "assistant" ? (
            <div className="message__markdown">
              <ReactMarkdown remarkPlugins={[remarkBreaks]} skipHtml>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : (
            <p>{message.content}</p>
          )
        )}
      </div>
    </article>
  );
}
