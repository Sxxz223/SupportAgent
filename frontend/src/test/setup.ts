import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());

Object.defineProperty(Element.prototype, "scrollIntoView", {
  configurable: true,
  value: () => undefined,
});

Object.defineProperty(URL, "createObjectURL", {
  configurable: true,
  value: () => "blob:test-image",
});

Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  value: () => undefined,
});
