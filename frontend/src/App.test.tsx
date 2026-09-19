import { StrictMode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { createSession, sendMessage, sendMultimodalMessage } from "./api/client";

vi.mock("./api/client", () => ({
  createSession: vi.fn(),
  sendMessage: vi.fn(),
  sendMultimodalMessage: vi.fn(),
}));

vi.mock("./components/GradientWaves", () => ({
  default: (props: { speed: number; amplitude: number; brightness: number }) => (
    <div
      data-testid="gradient-waves"
      data-speed={props.speed}
      data-amplitude={props.amplitude}
      data-brightness={props.brightness}
    />
  ),
}));

const createSessionMock = vi.mocked(createSession);
const sendMessageMock = vi.mocked(sendMessage);
const sendMultimodalMessageMock = vi.mocked(sendMultimodalMessage);


describe("App", () => {
  beforeEach(() => {
    createSessionMock.mockReset();
    sendMessageMock.mockReset();
    sendMultimodalMessageMock.mockReset();
    createSessionMock.mockResolvedValue("session-1");
    vi.spyOn(URL, "createObjectURL").mockReturnValueOnce("blob:input-preview").mockReturnValueOnce("blob:message-preview");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  it("creates one session and reuses it across messages", async () => {
    sendMessageMock
      .mockResolvedValueOnce({ reply: "Hello Alice", stage: "identify_product" })
      .mockResolvedValueOnce({ reply: "Tell me the issue", stage: "understand_issue" });
    const user = userEvent.setup();

    render(
      <StrictMode>
        <App />
      </StrictMode>,
    );

    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("gradient-waves")).toBeInTheDocument();
    expect(screen.getByTestId("gradient-waves").parentElement).toHaveAttribute("data-agent-status", "idle");
    const input = screen.getByLabelText("Message");
    await user.type(input, "I'm Alice.{enter}");
    expect(await screen.findByText("Hello Alice")).toBeInTheDocument();
    await user.type(input, "My product is Anker Prime Charger (250W, 6 Ports, GaNPrime).{enter}");
    expect(await screen.findByText("Tell me the issue")).toBeInTheDocument();

    expect(sendMessageMock).toHaveBeenNthCalledWith(1, "session-1", "I'm Alice.");
    expect(sendMessageMock).toHaveBeenNthCalledWith(
      2,
      "session-1",
      "My product is Anker Prime Charger (250W, 6 Ports, GaNPrime).",
    );
    expect(screen.queryByText(/Current stage:/)).not.toBeInTheDocument();
    expect(sendMultimodalMessageMock).not.toHaveBeenCalled();
  });

  it("shows a request error without crashing", async () => {
    sendMessageMock.mockRejectedValue(new Error("Backend unavailable"));
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(1));

    await user.type(screen.getByLabelText("Message"), "Hello{enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't reach support. Please try again in a moment.",
    );
    expect(screen.getByTestId("gradient-waves").parentElement).toHaveAttribute("data-agent-status", "idle");
    expect(screen.queryByText("Backend unavailable")).not.toBeInTheDocument();
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeEnabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("disables input and shows loading while a reply is pending", async () => {
    let resolveReply: ((value: { reply: string; stage: string }) => void) | undefined;
    sendMessageMock.mockReturnValue(new Promise((resolve) => {
      resolveReply = resolve;
    }));
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(1));

    await user.type(screen.getByLabelText("Message"), "Hello{enter}");

    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Thinking");
    expect(screen.getByTestId("gradient-waves")).toHaveAttribute("data-speed", "0.4");
    expect(screen.getByTestId("gradient-waves").parentElement).toHaveAttribute("data-agent-status", "thinking");
    expect(screen.getByLabelText("Message")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Please wait" })).toBeDisabled();
    await user.type(screen.getByLabelText("Message"), "duplicate{enter}");
    expect(sendMessageMock).toHaveBeenCalledTimes(1);
    resolveReply?.({ reply: "Hi", stage: "identify_user" });
    expect(await screen.findByText("Hi")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByTestId("gradient-waves").parentElement).toHaveAttribute("data-agent-status", "idle");
  });

  it("keeps Shift+Enter as a newline and rejects empty input", async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(1));
    const input = screen.getByLabelText("Message");

    await user.type(input, "Line one{shift>}{enter}{/shift}Line two");
    expect(input).toHaveValue("Line one\nLine two");
    expect(sendMessageMock).not.toHaveBeenCalled();
  });

  it("renders assistant Markdown while keeping user messages as plain text", async () => {
    sendMessageMock.mockResolvedValue({
      reply: "**Anker Prime Charger (250W, 6 Ports, GaNPrime)**\n\n- Clean the contacts\n- Reseat the robot\n\n1. Check the light\n2. Try again",
      stage: "diagnose",
    });
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(1));

    await user.type(screen.getByLabelText("Message"), "**literal user text**{enter}");

    expect(await screen.findByText("Anker Prime Charger (250W, 6 Ports, GaNPrime)")).toHaveProperty("tagName", "STRONG");
    expect(screen.getByText("Clean the contacts").closest("li")).not.toBeNull();
    expect(screen.getByText("Check the light").closest("ol")).not.toBeNull();
    expect(screen.getByText("**literal user text**")).toBeInTheDocument();
  });

  it("previews an image, sends it through the multimodal API, then clears selection", async () => {
    sendMultimodalMessageMock.mockResolvedValue({
      reply: "The charging contacts look dirty.",
      stage: "diagnose",
    });
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(1));
    const image = new File(["image bytes"], "prime-charger.png", { type: "image/png" });

    await user.upload(screen.getByLabelText("Attach image"), image);
    expect(screen.getByAltText("Selected preview")).toBeInTheDocument();
    expect(screen.getByText("prime-charger.png")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Message"), "Can you check this?{enter}");

    expect(await screen.findByText("The charging contacts look dirty.")).toBeInTheDocument();
    expect(sendMultimodalMessageMock).toHaveBeenCalledWith(
      "session-1",
      "Can you check this?",
      image,
    );
    expect(sendMessageMock).not.toHaveBeenCalled();
    expect(screen.queryByAltText("Selected preview")).not.toBeInTheDocument();
    expect(screen.getByAltText("Uploaded attachment")).toHaveAttribute(
      "src",
      "blob:message-preview",
    );
  });

  it("allows image-only messages and lets the user remove a selection", async () => {
    sendMultimodalMessageMock.mockResolvedValue({ reply: "Image received", stage: "identify_user" });
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(1));
    const image = new File(["image bytes"], "robot.webp", { type: "image/webp" });
    const input = screen.getByLabelText("Attach image");

    await user.upload(input, image);
    await user.click(screen.getByRole("button", { name: "Remove image" }));
    expect(screen.queryByAltText("Selected preview")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();

    await user.upload(input, image);
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Image received")).toBeInTheDocument();
    expect(sendMultimodalMessageMock).toHaveBeenCalledWith("session-1", "", image);
  });

  it("uses the same thinking state for a pending multimodal request", async () => {
    let resolveReply: ((value: { reply: string; stage: string }) => void) | undefined;
    sendMultimodalMessageMock.mockReturnValue(new Promise((resolve) => { resolveReply = resolve; }));
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(createSessionMock).toHaveBeenCalledTimes(1));
    const image = new File(["image bytes"], "charger.png", { type: "image/png" });

    await user.upload(screen.getByLabelText("Attach image"), image);
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(screen.getByAltText("Uploaded attachment")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Thinking");
    expect(screen.getByTestId("gradient-waves").parentElement).toHaveAttribute("data-agent-status", "thinking");
    resolveReply?.({ reply: "Image checked", stage: "diagnose" });
    expect(await screen.findByText("Image checked")).toBeInTheDocument();
    expect(screen.getByTestId("gradient-waves").parentElement).toHaveAttribute("data-agent-status", "idle");
  });
});
