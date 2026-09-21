export type SessionResponse = { session_id: string };

export type TaskStage = "confirmed" | "collecting" | "information_ready" | "judgement_formed" | "solution_provided" | "waiting_confirmation" | "completed";
export type TaskUpdate = { taskId: string; name: string; stage: TaskStage; statusText: string };
export type FocusPath = { currentState: string; knownFacts: string[]; currentJudgement: string; nextDirection: string };
export type SolutionPlan = { steps: Array<{ id: string; title: string; status: "done" | "current" | "pending" }>; revision_note?: string };
export type InteractionOption = { id?: string; label: string; value?: string; detail?: string };
export type Interaction = {
  type: "choice" | "choice_image" | "image" | "text" | "confirm" | "split_confirm" | "image_confirm" | "partial_reshoot" | "none";
  question?: string;
  options?: InteractionOption[];
  image?: { enabled: boolean; label: string; target: string; fields?: string[] };
  image_prompt?: string;
};
export type VisionField = { key: string; label: string; value: unknown; status: "recognized" | "unclear" | "failed"; source?: string };
export type ChatResponse = {
  reply: string;
  stage: string;
  turnId?: string;
  caseVersion?: number;
  factsUpdate?: Record<string, unknown>;
  taskDecision?: { type: "single" | "propose_split" | "confirmed" | "clarify" };
  taskUpdates?: TaskUpdate[];
  focusTaskId?: string;
  focusChanged?: boolean;
  focusChangeReason?: string;
  focusPath?: FocusPath;
  interaction?: Interaction;
  agentState?: { emoji: "thinking" | "investigating" | "insight" | "done_step" | "resolved" };
  emotionState?: { state: string; trend: string };
  visionResult?: { fields: VisionField[]; followUp?: { type: "partial_reshoot"; target: string } };
  plan?: SolutionPlan;
};
export type UiMessage = { id: string; role: "user" | "assistant" | "proactive"; content: string };
export type MessageRole = "user" | "assistant";
export type ChatMessage = { id: string; role: MessageRole; content: string; imageUrl?: string };
