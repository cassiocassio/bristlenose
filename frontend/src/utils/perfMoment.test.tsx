import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { markMomentEnd, resetPerfMoments, useMomentOnPaint } from "./perfMoment";

type Posted = { type: string; name: string };
let posted: Posted[];

function Probe(props: { ready: boolean; k?: string; once?: boolean }) {
  useMomentOnPaint("open-transcript", props.ready, props.k ?? null, props.once);
  return null;
}

async function twoFrames() {
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(null))));
  await new Promise((r) => setTimeout(r, 0));
}

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

describe("perfMoment", () => {
  it("posts the mark to the navigation handler and leaves a performance mark", () => {
    const mark = vi.spyOn(performance, "mark");
    markMomentEnd("first-card-painted");
    expect(posted).toEqual([{ type: "perf-mark", name: "first-card-painted" }]);
    expect(mark).toHaveBeenCalledWith("bn.first-card-painted.end");
  });

  it("does nothing outside the Mac app", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (window as any).webkit;
    expect(() => markMomentEnd("open-transcript")).not.toThrow();
  });

  it("waits for the content, then two frames", async () => {
    const { rerender } = render(<Probe ready={false} />);
    await twoFrames();
    expect(posted).toHaveLength(0);
    rerender(<Probe ready />);
    expect(posted).toHaveLength(0);
    await twoFrames();
    expect(posted).toEqual([{ type: "perf-mark", name: "open-transcript" }]);
  });

  it("ends again for a different key, but only once per page when asked", async () => {
    const { rerender } = render(<Probe ready k="a" />);
    await twoFrames();
    rerender(<Probe ready k="b" />);
    await twoFrames();
    expect(posted).toHaveLength(2);

    posted.length = 0;
    resetPerfMoments();
    const once = render(<Probe ready k="a" once />);
    await twoFrames();
    once.rerender(<Probe ready k="b" once />);
    await twoFrames();
    expect(posted).toHaveLength(1);
  });

  it("does not post if the content went away before the second frame", async () => {
    const { unmount } = render(<Probe ready />);
    unmount();
    await twoFrames();
    expect(posted).toHaveLength(0);
  });
});
