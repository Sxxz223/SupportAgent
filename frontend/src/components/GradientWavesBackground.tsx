import { useEffect, useMemo, useRef, useState } from "react";

import GradientWaves from "./GradientWaves";

export type AgentStatus = "idle" | "thinking";

type Props = {
  status: AgentStatus;
};

type WaveConfig = {
  horizonColor: string;
  waveColor: string;
  crestColor: string;
  speed: number;
  amplitude: number;
  swell: number;
  turbulence: number;
  brightness: number;
};

const IDLE: WaveConfig = {
  horizonColor: "#0070ff",
  waveColor: "#313fe7",
  crestColor: "#ffffff",
  speed: 0.4,
  amplitude: 2.5,
  swell: 35,
  turbulence: 20,
  brightness: 1.0,
};

const THINKING: WaveConfig = {
  horizonColor: "#5b00dc",
  waveColor: "#3700fc",
  crestColor: "#ffffff",
  speed: 0.6,
  amplitude: 2.9,
  swell: 39,
  turbulence: 23,
  brightness: 1.05,
};

const NUMBER_KEYS = ["speed", "amplitude", "swell", "turbulence", "brightness"] as const;
const COLOR_KEYS = ["horizonColor", "waveColor", "crestColor"] as const;

function easeInOutCubic(value: number) {
  return value < 0.5
    ? 4 * value * value * value
    : 1 - Math.pow(-2 * value + 2, 3) / 2;
}

function hexToRgb(hex: string) {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
}

function rgbToHex(rgb: number[]) {
  return `#${rgb.map((channel) => Math.round(channel).toString(16).padStart(2, "0")).join("")}`;
}

function interpolateColor(from: string, to: string, progress: number) {
  const start = hexToRgb(from);
  const end = hexToRgb(to);
  return rgbToHex(start.map((channel, index) => channel + (end[index] - channel) * progress));
}

function interpolateConfig(from: WaveConfig, to: WaveConfig, progress: number): WaveConfig {
  const result = {} as WaveConfig;
  NUMBER_KEYS.forEach((key) => { result[key] = from[key] + (to[key] - from[key]) * progress; });
  COLOR_KEYS.forEach((key) => { result[key] = interpolateColor(from[key], to[key], progress); });
  return result;
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  );

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!query) return;
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener?.("change", update);
    return () => query.removeEventListener?.("change", update);
  }, []);

  return reduced;
}

function useAnimatedWaveConfig(target: WaveConfig, status: AgentStatus) {
  const [animated, setAnimated] = useState<WaveConfig>(IDLE);
  const currentRef = useRef<WaveConfig>(IDLE);

  useEffect(() => {
    const start = { ...currentRef.current };
    const duration = status === "thinking" ? 1050 : 1400;
    let startedAt: number | null = null;
    let frame = 0;

    const animate = (timestamp: number) => {
      if (startedAt === null) startedAt = timestamp;
      const elapsed = timestamp - startedAt;
      const progress = Math.min(elapsed / duration, 1);
      const next = progress === 1
        ? target
        : interpolateConfig(start, target, easeInOutCubic(progress));
      currentRef.current = next;
      setAnimated(next);
      if (progress < 1) frame = requestAnimationFrame(animate);
    };

    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [target, status]);

  return animated;
}

export default function GradientWavesBackground({ status }: Props) {
  const reducedMotion = useReducedMotion();
  const target = useMemo<WaveConfig>(() => {
    if (status === "idle") return IDLE;
    if (!reducedMotion) return THINKING;
    return {
      ...THINKING,
      speed: IDLE.speed,
      amplitude: IDLE.amplitude,
      swell: IDLE.swell,
      turbulence: IDLE.turbulence,
    };
  }, [status, reducedMotion]);
  const visual = useAnimatedWaveConfig(target, status);

  return (
    <div
      className={`gradient-waves-background gradient-waves-background--${status}`}
      data-agent-status={status}
    >
      <GradientWaves
        horizonColor={visual.horizonColor}
        waveColor={visual.waveColor}
        crestColor={visual.crestColor}
        speed={visual.speed}
        amplitude={visual.amplitude}
        waveScale={0.6}
        waveRatio={0.9}
        swell={visual.swell}
        turbulence={visual.turbulence}
        tilt={1.11}
        zoom={1.0}
        height={5.5}
        fogDepth={15}
        detail="medium"
        brightness={visual.brightness}
        opacity={1.0}
        mouseInteraction={true}
        parallaxStrength={0.5}
        grain={true}
        grainIntensity={0.05}
      />
    </div>
  );
}
