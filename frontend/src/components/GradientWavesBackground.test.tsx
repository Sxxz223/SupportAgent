import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import GradientWavesBackground from "./GradientWavesBackground";

vi.mock("./GradientWaves", () => ({
  default: (props: {
    speed: number;
    amplitude: number;
    swell: number;
    turbulence: number;
    horizonColor: string;
    waveColor: string;
  }) => (
    <div
      data-testid="waves"
      data-speed={props.speed}
      data-amplitude={props.amplitude}
      data-swell={props.swell}
      data-turbulence={props.turbulence}
      data-horizon={props.horizonColor}
      data-wave={props.waveColor}
    />
  ),
}));

describe("GradientWavesBackground", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function controlledAnimationFrames() {
    let nextId = 0;
    const callbacks = new Map<number, FrameRequestCallback>();
    vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => {
      const id = ++nextId;
      callbacks.set(id, callback);
      return id;
    }));
    vi.stubGlobal("cancelAnimationFrame", vi.fn((id: number) => callbacks.delete(id)));
    return (timestamp: number) => {
      const pending = [...callbacks.values()];
      callbacks.clear();
      act(() => pending.forEach((callback) => callback(timestamp)));
    };
  }

  it("interpolates into thinking and back to idle without remounting", () => {
    const step = controlledAnimationFrames();
    const view = render(<GradientWavesBackground status="idle" />);
    const waves = screen.getByTestId("waves");

    view.rerender(<GradientWavesBackground status="thinking" />);
    expect(screen.getByTestId("waves")).toBe(waves);
    expect(waves).toHaveAttribute("data-horizon", "#0070ff");
    step(0);
    step(525);

    expect(screen.getByTestId("waves")).toBe(waves);
    expect(waves.getAttribute("data-horizon")).not.toBe("#0070ff");
    expect(waves.getAttribute("data-horizon")).not.toBe("#5b00dc");
    expect(Number(waves.getAttribute("data-speed"))).toBeGreaterThan(0.4);
    expect(Number(waves.getAttribute("data-speed"))).toBeLessThan(0.6);

    step(1050);
    expect(waves).toHaveAttribute("data-horizon", "#5b00dc");
    expect(waves).toHaveAttribute("data-wave", "#3700fc");
    expect(waves).toHaveAttribute("data-speed", "0.6");

    view.rerender(<GradientWavesBackground status="idle" />);
    step(2000);
    step(3400);
    expect(screen.getByTestId("waves")).toBe(waves);
    expect(waves).toHaveAttribute("data-horizon", "#0070ff");
    expect(waves).toHaveAttribute("data-speed", "0.4");
  });

  it("keeps motion calm under the reduced-motion preference", () => {
    const step = controlledAnimationFrames();
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    render(<GradientWavesBackground status="thinking" />);
    step(0);
    step(1050);

    expect(screen.getByTestId("waves")).toHaveAttribute("data-speed", "0.4");
    expect(screen.getByTestId("waves")).toHaveAttribute("data-amplitude", "2.5");
    expect(screen.getByTestId("waves")).toHaveAttribute("data-swell", "35");
    expect(screen.getByTestId("waves")).toHaveAttribute("data-turbulence", "20");
    expect(screen.getByTestId("waves")).toHaveAttribute("data-horizon", "#5b00dc");
  });
});
