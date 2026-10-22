/**
 * The panel's own state: the bar and Stop. Only the panel's elements are faked,
 * as plain objects with the few members ui.ts touches; the Figma side is not
 * mocked at all — its messages are what the test sends.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Listener = (e: any) => void;

function element(hidden = false) {
  const classes = new Set<string>();
  const listeners: Record<string, Listener[]> = {};
  return {
    hidden,
    disabled: false,
    textContent: "",
    value: "",
    style: {} as Record<string, string>,
    classList: {
      add: (c: string) => void classes.add(c),
      remove: (c: string) => void classes.delete(c),
      contains: (c: string) => classes.has(c),
      toggle: (c: string, on?: boolean) => {
        if (on ?? !classes.has(c)) classes.add(c);
        else classes.delete(c);
      },
    },
    addEventListener: (type: string, fn: Listener) => (listeners[type] ??= []).push(fn),
    fire: (type: string, e: unknown = {}) => listeners[type]?.forEach((fn) => fn(e)),
  };
}

let els: Record<string, ReturnType<typeof element>>;
let docListeners: Record<string, Listener[]>;
let win: { onmessage?: (e: { data: unknown }) => void };

const fromCode = (pluginMessage: unknown) => win.onmessage?.({ data: { pluginMessage } });

beforeEach(async () => {
  els = {
    file: element(),
    drop: element(),
    status: element(),
    bar: element(),
    fill: element(),
    stop: element(true), // hidden in ui.html until a build starts
  };
  docListeners = {};
  win = {};
  vi.stubGlobal("document", {
    getElementById: (id: string) => els[id],
    addEventListener: (type: string, fn: Listener) => (docListeners[type] ??= []).push(fn),
  });
  vi.stubGlobal("window", win);
  vi.stubGlobal("parent", { postMessage: vi.fn() });
  vi.resetModules();
  await import("./ui");
});

afterEach(() => vi.unstubAllGlobals());

describe("panel progress", () => {
  it("a file dropped on the canvas shows the bar and Stop, and an error hides them", () => {
    // The canvas drop goes straight to the plugin's code; the panel only hears progress.
    fromCode({ type: "progress", done: 0, total: 4 });
    expect(els.bar.classList.contains("on")).toBe(true);
    expect(els.stop.hidden).toBe(false);
    expect(els.stop.disabled).toBe(false);
    expect(els.status.textContent).toBe("Building the board… 0 of 4 quotes");

    fromCode({ type: "failed", message: "Stopped after 1 of 4 quotes. Undo removes what was drawn; then try again." });
    expect(els.bar.classList.contains("on")).toBe(false);
    expect(els.stop.hidden).toBe(true);
  });

  it("a Stop pressed during a build stays pressed when the next count arrives", () => {
    const paste = { clipboardData: { getData: () => "{}" }, preventDefault: () => {} };
    docListeners.paste.forEach((fn) => fn(paste));
    expect(els.bar.classList.contains("on")).toBe(true);
    expect(els.stop.hidden).toBe(false);

    els.stop.fire("click");
    fromCode({ type: "progress", done: 2, total: 4 });
    expect(els.stop.disabled).toBe(true);
    expect(els.status.textContent).toBe("Stopping…");
  });
});
