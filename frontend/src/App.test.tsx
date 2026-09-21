import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { createSession, reportActivity, resumeSession, sendMessage, sendMultimodalMessage } from "./api/client";

vi.mock("./api/client", () => ({
  createSession: vi.fn(), sendMessage: vi.fn(), sendMultimodalMessage: vi.fn(),
  resumeSession: vi.fn(),
  reportActivity: vi.fn(() => Promise.resolve()),
  getSessionEventsUrl: vi.fn(() => "http://events"),
}));
class EventSourceStub {
  static latest: EventSourceStub | null = null;
  listeners: Record<string, (event: MessageEvent) => void> = {};
  addEventListener = vi.fn((type: string, listener: EventListener) => {
    this.listeners[type] = listener as (event: MessageEvent) => void;
  });
  close = vi.fn();
  constructor(_url: string) { EventSourceStub.latest = this; }
  emit(type: string, payload: unknown) {
    this.listeners[type]?.({ data: JSON.stringify(payload) } as MessageEvent);
  }
}
vi.stubGlobal("EventSource", EventSourceStub);
const createSessionMock = vi.mocked(createSession);
const resumeSessionMock = vi.mocked(resumeSession);
const sendMessageMock = vi.mocked(sendMessage);
const sendImageMock = vi.mocked(sendMultimodalMessage);
const reportActivityMock = vi.mocked(reportActivity);

describe("service workspace", () => {
  beforeEach(() => {
    createSessionMock.mockReset().mockResolvedValue("session-1");
    resumeSessionMock.mockReset(); window.localStorage.clear();
    sendMessageMock.mockReset(); sendImageMock.mockReset();
    reportActivityMock.mockReset().mockResolvedValue(undefined);
    EventSourceStub.latest = null;
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:preview");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  it("renders API-owned focus, choices, tasks and fixed stage progress", async () => {
    sendMessageMock.mockResolvedValue({
      reply: "我先确认当前连接状态。", stage: "diagnose",
      taskDecision: { type: "confirmed" },
      taskUpdates: [
        { taskId: "charging", name: "充电异常", stage: "collecting", statusText: "正在确认连接状态" },
        { taskId: "return", name: "退货判断", stage: "information_ready", statusText: "信息已齐全" },
      ],
      focusTaskId: "charging",
      focusPath: { currentState: "正在定位异常", knownFacts: ["换线后仍无效"], currentJudgement: "需要确认接口", nextDirection: "确认当前接口" },
      plan: { steps: [
        { id: "model", title: "确定产品型号", status: "done" },
        { id: "port", title: "确认当前接口", status: "current" },
        { id: "verify", title: "验证充电状态", status: "pending" },
      ], revision_note: "换线无效，改为检查接口" },
      interaction: { type: "choice", question: "当前连接的是哪个接口？", options: [{ id: "c1", label: "USB-C 1" }, { id: "c2", label: "USB-C 2" }] },
      agentState: { emoji: "🤗", label: "陪你一起处理" },
    });
    const user = userEvent.setup(); render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "充电宝不能充电，也想了解退货{enter}");
    expect(await screen.findByText("当前连接的是哪个接口？")).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "USB-C 1" })).toBeInTheDocument();
    expect(screen.getByText("陪你一起处理")).toBeInTheDocument();
    expect(screen.getByText("确定产品型号")).toBeInTheDocument();
    expect(screen.getByText("确认当前接口", { selector: ".solution-path span" })).toBeInTheDocument();
    expect(screen.getByText("路径已更新：换线无效，改为检查接口")).toBeInTheDocument();
  });

  it("shows image input only when the API enables it", async () => {
    sendMessageMock.mockResolvedValue({
      reply: "可以拍给我看。", stage: "diagnose",
      interaction: { type: "choice_image", question: "当前是哪个接口？", options: [], image: { enabled: true, label: "拍给 AI 看", target: "当前线材连接位置" } },
    });
    const user = userEvent.setup(); render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    expect(screen.queryByLabelText("上传图片")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("输入消息"), "我不知道这是哪个接口{enter}");
    expect(await screen.findByLabelText("上传图片")).toBeInTheDocument();
    expect(screen.getByText("当前线材连接位置")).toBeInTheDocument();
  });

  it("renders split confirmation as the only formal action", async () => {
    sendMessageMock.mockResolvedValue({
      reply: "我理解你有两个目标。", stage: "diagnose",
      taskDecision: { type: "propose_split" },
      interaction: { type: "split_confirm", question: "要分别记录这两个问题吗？", options: [
        { id: "accurate", label: "拆分准确", value: "split_confirm:accurate" }, { id: "edit", label: "需要修改", value: "split_confirm:edit" },
      ] },
    });
    const user = userEvent.setup(); render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "不能充电，不修的话还想退货{enter}");
    expect(await screen.findByRole("button", { name: "拆分准确" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "需要修改" })).toBeInTheDocument();
  });

  it("keeps a failed message available for retry", async () => {
    sendMessageMock.mockRejectedValueOnce(new Error("down")).mockResolvedValueOnce({ reply: "已恢复", stage: "diagnose", interaction: { type: "text" } });
    const user = userEvent.setup(); render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "你好{enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("内容已保留");
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText("已恢复")).toBeInTheDocument();
  });

  it("restores the existing case after a page reload", async () => {
    window.localStorage.setItem("anker-support-session", "saved-session");
    resumeSessionMock.mockResolvedValue({
      session_id: "saved-session", stage: "diagnose", caseVersion: 3, turnId: "turn_003",
      messages: [{ id: "history-1", role: "assistant", content: "继续排查充电问题" }],
      taskUpdates: [{ taskId: "charging", name: "充电异常", stage: "collecting", statusText: "正在确认接口" }],
      focusTaskId: "charging",
      focusPath: { currentState: "正在确认接口", knownFacts: ["型号 A2345"], currentJudgement: "需要检查连接", nextDirection: "确认接口" },
      plan: { steps: [{ id: "port", title: "确认当前接口", status: "current" }] },
      interaction: { type: "choice", question: "当前使用哪个接口？", options: [{ label: "USB-C1" }] },
    });
    render(<App />);
    expect(await screen.findByText("继续排查充电问题")).toBeInTheDocument();
    expect(screen.getByText("确认当前接口", { selector: ".solution-path span" })).toBeInTheDocument();
    expect(createSessionMock).not.toHaveBeenCalled();
  });

  it("shows the clicked Chinese label while sending the machine value", async () => {
    sendMessageMock
      .mockResolvedValueOnce({
        reply: "请选择型号。", stage: "diagnose", turnId: "turn_001", caseVersion: 1,
        interaction: { type: "choice", question: "这是哪个型号？", options: [
          { id: "a2345", label: "Anker Prime 250W", value: "charger_model:A2345" },
        ] },
        agentState: { emoji: "🙂", label: "耐心陪你确认" },
      })
      .mockResolvedValueOnce({ reply: "型号已记录。", stage: "diagnose", interaction: { type: "text" }, agentState: { emoji: "😊", label: "很高兴确认清楚" } });
    const user = userEvent.setup(); render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "我不确定型号{enter}");
    await user.click(await screen.findByRole("button", { name: "Anker Prime 250W" }));
    expect(sendMessageMock).toHaveBeenLastCalledWith("session-1", "charger_model:A2345");
    expect(screen.getByText("Anker Prime 250W", { selector: ".stream-message p" })).toBeInTheDocument();
    expect(screen.queryByText("charger_model:A2345", { selector: ".stream-message p" })).not.toBeInTheDocument();
  });

  it("keeps each reply emoji and renders a later proactive question", async () => {
    sendMessageMock
      .mockResolvedValueOnce({
        reply: "我理解这确实让人着急。", stage: "diagnose", turnId: "turn_001", caseVersion: 1,
        interaction: { type: "text" }, agentState: { emoji: "🥺", label: "有些心疼你的体验" },
      })
      .mockResolvedValueOnce({
        reply: "好消息，我们找到方向了。", stage: "diagnose", turnId: "turn_002", caseVersion: 2,
        interaction: { type: "none" }, agentState: { emoji: "😄", label: "替你松了口气" },
      });
    const user = userEvent.setup(); const { container } = render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "真的很着急{enter}");
    await user.type(screen.getByLabelText("输入消息"), "已经有线索了{enter}");
    const replyEmojis = Array.from(container.querySelectorAll(".stream-message.is-assistant b")).map((node) => node.textContent);
    expect(replyEmojis).toContain("🥺");
    expect(replyEmojis).toContain("😄");

    EventSourceStub.latest?.emit("proactive_message", {
      id: "follow-1", content: "操作进行得怎么样了？", turnId: "turn_002", caseVersion: 2,
      agentState: { emoji: "🤗", label: "惦记着进展" },
    });
    EventSourceStub.latest?.emit("interaction_update", {
      turnId: "turn_002", caseVersion: 2,
      interaction: { type: "choice", question: "现在进展怎么样？", options: [{ label: "已经完成" }] },
    });
    expect(await screen.findByText("操作进行得怎么样了？")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "已经完成" })).toBeInTheDocument();
    expect(replyEmojis).toContain("🥺");
  });

  it("accepts the Agent introduction after starting over", async () => {
    createSessionMock.mockResolvedValueOnce("session-1").mockResolvedValueOnce("session-2");
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.click(screen.getByRole("button", { name: "重新开始" }));
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(EventSourceStub.latest).not.toBeNull());
    EventSourceStub.latest?.emit("proactive_message", {
      id: "intro-2", content: "你好，我是 Anker 智能服务助手。",
      turnId: "turn_000", caseVersion: 0,
      agentState: { emoji: "👋", label: "很高兴认识你" },
    });
    expect(await screen.findByText("你好，我是 Anker 智能服务助手。")).toBeInTheDocument();
  });
});
