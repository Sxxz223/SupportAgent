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
  interaction?: {
    type: "choice" | "image" | "text" | "confirm" | "none";
    options?: Array<{ id?: string; label: string; value?: string; detail?: string }>;
    image_prompt?: string;
  };
  plan?: {
    steps: Array<{ id: string; title: string; status: "done" | "current" | "pending" }>;
    progress?: number;
    revision_note?: string;
  };
  facts_update?: Record<string, string>;
};
