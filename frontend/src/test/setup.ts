import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { MotionGlobalConfig } from "motion/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { resetDb, server } from "./server";

// Animations never finish in jsdom (no real frames), so exiting rows would linger. Jump to the end.
MotionGlobalConfig.skipAnimations = true;

// jsdom's FormData is not understood by Node's fetch (it is sent as the text "[object FormData]"),
// so uploads in tests use Node's own FormData, borrowed from a real Response.
if (typeof window !== "undefined") {
  const nodeForm = await new Response("probe=1", {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  }).formData();
  globalThis.FormData = nodeForm.constructor as typeof FormData;
}

// jsdom has no matchMedia; the toast library needs it. The stub reports a light-mode system.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  });
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetDb();
  if (typeof window === "undefined") return; // node-environment tests (e.g. the schema check)
  window.localStorage.clear();
  document.documentElement.classList.remove("dark");
});
afterAll(() => server.close());
