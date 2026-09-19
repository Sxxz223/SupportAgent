import { afterEach, describe, expect, it, vi } from "vitest";

import { createSession, deleteCustomer, sendMessage, sendMultimodalMessage } from "./client";


describe("API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a backend session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ session_id: "session-1" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createSession()).resolves.toBe("session-1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/session",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("sends the session id and message to chat", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ reply: "Hello Alice", stage: "identify_product" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);

    await sendMessage("session-1", "I'm Alice.");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      session_id: "session-1",
      message: "I'm Alice.",
    });
  });

  it("sends image requests as browser-managed multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ reply: "I checked the image", stage: "diagnose" }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ));
    vi.stubGlobal("fetch", fetchMock);
    const image = new File(["image bytes"], "robot.png", { type: "image/png" });

    await sendMultimodalMessage("session-1", "Check this", image);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/chat/multimodal");
    expect(init.body).toBeInstanceOf(FormData);
    const body = init.body as FormData;
    expect(body.get("session_id")).toBe("session-1");
    expect(body.get("message")).toBe("Check this");
    expect(body.get("image")).toBe(image);
    expect(new Headers(init.headers).has("Content-Type")).toBe(false);
  });

  it("supports empty 204 responses from Admin delete endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteCustomer("customer/a")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/admin/customers/customer%2Fa",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
