import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as exportData from "./exportData";
import { markMomentEnd, resetPerfMoments, useMomentOnPaint } from "./perfMoment";

type Posted = { type: string; name: string };
let posted: Posted[];

function Probe(props: { ready: boolean; k?: string | null; once?: boolean; name?: "open-transcript" | "first-card-painted" }) {
  useMomentOnPaint(props.name ?? "open-transcript", props.ready, props.k ?? null, props.once);
  return null;
}

const frames = async (n = 2) => {
  for (let i = 0; i < n; i++) await new Promise((r) => requestAnimationFrame(() => r(null)));
  await new Promise((r) => setTimeout(r, 0));
};

beforeEach(() => {
  posted = [];
  resetPerfMoments();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).webkit = { messageHandlers: { navigation: { postMessage: (m: Posted) => posted.push(m) } } };
});
afterEach(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (window as any).webkit;
  vi.restoreAllMocks();
});

describe("perfMoment, attacked", () => {
  it("a thousand key changes before the second frame post once, for the last key", async () => {
    const { rerender } = render(<Probe ready k="0" />);
    for (let i = 1; i <= 1000; i++) rerender(<Probe ready k={String(i)} />);
    await frames();
    expect(posted).toHaveLength(1);
  });

  it("a handler that throws never breaks the page", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).webkit = { messageHandlers: { navigation: { postMessage: () => { throw new Error("handler gone"); } } } };
    expect(() => markMomentEnd("first-card-painted")).not.toThrow();
    render(<Probe ready />);
    await frames();
  });

  it("a webkit object with no handlers, or a null handler, is survivable", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).webkit = {};
    expect(() => markMomentEnd("open-transcript")).not.toThrow();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).webkit = { messageHandlers: { navigation: null } };
    expect(() => markMomentEnd("open-transcript")).not.toThrow();
  });

  it("performance.mark throwing does not stop the native post", () => {
    vi.spyOn(performance, "mark").mockImplementation(() => { throw new Error("no marks here"); });
    markMomentEnd("open-transcript");
    expect(posted).toEqual([{ type: "perf-mark", name: "open-transcript" }]);
  });

  it("in the HTML export it posts nothing and marks nothing", async () => {
    vi.spyOn(exportData, "isExportMode").mockReturnValue(true);
    const mark = vi.spyOn(performance, "mark");
    markMomentEnd("open-transcript");
    render(<Probe ready />);
    await frames();
    expect(posted).toHaveLength(0);
    expect(mark).not.toHaveBeenCalled();
  });

  it("flipping ready off and on between frames does not double-post", async () => {
    const { rerender } = render(<Probe ready />);
    rerender(<Probe ready={false} />);
    rerender(<Probe ready />);
    await frames();
    expect(posted).toHaveLength(1);
  });

  it("two moments are independent: once-per-page on one does not silence the other", async () => {
    render(<Probe ready once name="first-card-painted" />);
    render(<Probe ready once name="open-transcript" />);
    await frames();
    expect(posted.map((p) => p.name).sort()).toEqual(["first-card-painted", "open-transcript"]);
  });

  it("once-per-page survives the component being remounted", async () => {
    const a = render(<Probe ready once name="first-card-painted" />);
    await frames();
    a.unmount();
    render(<Probe ready once name="first-card-painted" />);
    await frames();
    expect(posted.filter((p) => p.name === "first-card-painted")).toHaveLength(1);
  });

  it("unmounting before the first frame cancels both frames", async () => {
    const cancel = vi.spyOn(window, "cancelAnimationFrame");
    const { unmount } = render(<Probe ready />);
    unmount();
    await frames();
    expect(posted).toHaveLength(0);
    expect(cancel).toHaveBeenCalled();
  });
});
