export type MessageRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: MessageRole;
  content: string;
  imageUrl?: string;
};

export type SessionResponse = {
  session_id: string;
};

export type ChatResponse = {
  reply: string;
  stage: string;
};
