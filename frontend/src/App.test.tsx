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

  it("shows only the customer flow and follows backend stages", async () => {
    sendMessageMock.mockResolvedValue({ reply: "请提供订单信息", stage: "verify_identity" });
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
    expect(screen.queryByText(/密钥|连接方式|后端同步|TEAM PREVIEW/)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("输入消息"), "我是 Alice{enter}");
    expect(await screen.findByText("请提供订单信息")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "核验购买信息。" })).toBeInTheDocument();
    expect(screen.getByText("核验购买身份").closest("li")).toHaveAttribute("aria-current", "step");
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
    sendMultimodalMessageMock.mockResolvedValue({ reply: "图片已分析", stage: "diagnose" });
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledOnce());
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
