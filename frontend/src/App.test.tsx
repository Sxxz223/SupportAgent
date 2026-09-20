import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { createSession, sendMessage, sendMultimodalMessage } from "./api/client";

vi.mock("./api/client", () => ({
  createSession: vi.fn(), sendMessage: vi.fn(), sendMultimodalMessage: vi.fn(),
}));
const createSessionMock = vi.mocked(createSession);
const sendMessageMock = vi.mocked(sendMessage);
const sendMultimodalMessageMock = vi.mocked(sendMultimodalMessage);

describe("customer service page", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
    createSessionMock.mockReset().mockResolvedValue("session-1");
    sendMessageMock.mockReset();
    sendMultimodalMessageMock.mockReset();
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:preview");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  it("starts without a path and renders only the path returned by the agent", async () => {
    sendMessageMock.mockResolvedValue({ reply: "先确认一下具体表现", stage: "diagnose", plan: { steps: [
      { id: "understand", title: "确认故障现象", status: "current" },
      { id: "test", title: "测试连接状态", status: "pending" },
    ], progress: 20 }, interaction: { type: "choice", options: [{ label: "完全没有反应" }, { label: "会短暂连接" }] } });
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    expect(screen.queryByText(/密钥|连接方式|后端同步|TEAM PREVIEW/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("解决路径")).toBeInTheDocument();
    expect(screen.getByLabelText("路径将在分析后显示")).toBeInTheDocument();
    await user.type(screen.getByLabelText("输入消息"), "充电宝突然不能给电脑充电了{enter}");
    expect(await screen.findByText("先确认一下具体表现")).toBeInTheDocument();
    expect(screen.getAllByText("确认故障现象").find((node) => node.closest("li"))?.closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("button", { name: /完全没有反应/ })).toBeInTheDocument();
  });

  it("keeps failed content available for retry", async () => {
    sendMessageMock.mockRejectedValueOnce(new Error("down")).mockResolvedValueOnce({ reply: "已恢复", stage: "identify_user" });
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "你好{enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("内容已保留");
    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText("已恢复")).toBeInTheDocument();
  });

  it("validates and sends a customer photo", async () => {
    sendMessageMock.mockResolvedValue({ reply: "请拍一下接口位置", stage: "diagnose", interaction: { type: "image", image_prompt: "请把接口和旁边的标识一起拍进去" } });
    sendMultimodalMessageMock.mockResolvedValue({ reply: "图片已分析", stage: "diagnose" });
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    await user.type(screen.getByLabelText("输入消息"), "我不知道插的是哪个口{enter}");
    await screen.findByText("请拍一下接口位置");
    const invalid = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "large.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("上传图片"), invalid);
    expect(screen.getByRole("alert")).toHaveTextContent("不超过 10 MB");
    const image = new File(["image"], "device.png", { type: "image/png" });
    await user.upload(screen.getByLabelText("上传图片"), image);
    await user.click(screen.getByRole("button", { name: "发送消息" }));
    expect(await screen.findByText("图片已分析")).toBeInTheDocument();
  });

  it("keeps the demo on a separate URL and waits at 99 percent for confirmation", async () => {
    window.history.pushState({}, "", "/demo");
    const user = userEvent.setup();
    render(<App />);
    expect(createSessionMock).not.toHaveBeenCalled();
    expect(screen.queryByText("演示体验")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("输入消息"), "我的充电宝突然不能给电脑充电了{enter}");
    await user.click(screen.getByRole("button", { name: /Anker Prime Charger/ }));
    await user.click(await screen.findByRole("button", { name: /完全没有充电反应/ }));
    await user.click(await screen.findByRole("button", { name: /更换后恢复正常/ }));
    await user.click(await screen.findByRole("button", { name: /现在可以正常充电/ }));
    expect(await screen.findByRole("heading", { name: "确认问题解决" })).toBeInTheDocument();
    expect(screen.getAllByText("99").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: /已经解决/ }));
    expect(await screen.findByText("这一次，我们一起解决了。")).toBeInTheDocument();
    expect(screen.getAllByText("100").length).toBeGreaterThan(0);
  });
});
