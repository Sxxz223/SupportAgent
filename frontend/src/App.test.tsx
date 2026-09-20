import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { createSession, sendMessage, sendMultimodalMessage } from "./api/client";

vi.mock("./api/client", () => ({
  createSession: vi.fn(), sendMessage: vi.fn(), sendMultimodalMessage: vi.fn(),
  getSessionEventsUrl: vi.fn(() => "http://events"),
}));
class EventSourceStub {
  addEventListener = vi.fn();
  close = vi.fn();
  constructor(_url: string) {}
}
vi.stubGlobal("EventSource", EventSourceStub);
const createSessionMock = vi.mocked(createSession);
const sendMessageMock = vi.mocked(sendMessage);
const sendImageMock = vi.mocked(sendMultimodalMessage);

describe("service workspace", () => {
  beforeEach(() => {
    createSessionMock.mockReset().mockResolvedValue("session-1");
    sendMessageMock.mockReset(); sendImageMock.mockReset();
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
      interaction: { type: "choice", question: "当前连接的是哪个接口？", options: [{ id: "c1", label: "USB-C 1" }, { id: "c2", label: "USB-C 2" }] },
      agentState: { emoji: "investigating" },
    });
    const user = userEvent.setup(); render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "充电宝不能充电，也想了解退货{enter}");
    expect(await screen.findByText("当前连接的是哪个接口？")).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "USB-C 1" })).toBeInTheDocument();
    expect(screen.getByText("正在排查")).toBeInTheDocument();
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
        { id: "split", label: "分开处理" }, { id: "single", label: "保持一个任务" }, { id: "edit", label: "修改" },
      ] },
    });
    const user = userEvent.setup(); render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "不能充电，不修的话还想退货{enter}");
    expect(await screen.findByRole("button", { name: "分开处理" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保持一个任务" })).toBeInTheDocument();
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
});
