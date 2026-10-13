import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { frameIndexAt, framesFor, resetTapestryThumb, tapestryThumb } from "./tapestryThumb";
import type { TurnFrame } from "./types";

vi.mock("./api", () => ({ apiGet: vi.fn() }));
vi.mock("./exportData", () => ({ isExportMode: vi.fn(() => false) }));
import { apiGet } from "./api";
import { isExportMode } from "./exportData";

// One participant turn 30–400 s with a colour change at 200, and a second turn 450–600.
const frames: TurnFrame[] = [
  { t: 72.5, a: 30, b: 200, change: false, src: "data:a" },
  { t: 202, a: 200, b: 400, change: true, src: "data:b" },
  { t: 487.5, a: 450, b: 600, change: false, src: "data:c" },
];

// Read the controller's published view through its hook's store: a component would subscribe.
import { useTapestryThumb } from "./tapestryThumb";
import { renderHook } from "@testing-library/react";
const view = () => renderHook(() => useTapestryThumb()).result.current;

beforeEach(() => {
  vi.useFakeTimers();
  resetTapestryThumb();
});
afterEach(() => {
  resetTapestryThumb();
  vi.useRealTimers();
});

describe("frameIndexAt", () => {
  it("finds the stretch under the pointer", () => {
    expect(frameIndexAt(frames, 100)).toBe(0);
    expect(frameIndexAt(frames, 200)).toBe(1);
    expect(frameIndexAt(frames, 500)).toBe(2);
  });
  it("holds the last participant frame over a moderator turn", () => {
    expect(frameIndexAt(frames, 420)).toBe(1);
  });
  it("shows the first frame before the first participant turn, and nothing without frames", () => {
    expect(frameIndexAt(frames, 5)).toBe(0);
    expect(frameIndexAt([], 5)).toBe(-1);
  });
});

describe("the hover thumbnail", () => {
  const rest = (sec: number, sid = "s1") => tapestryThumb.move(sid, frames, sec, 300);

  it("opens only after the pointer has rested 700 ms", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(699);
    expect(view()).toBeNull();
    vi.advanceTimersByTime(1);
    expect(view()?.index).toBe(0);
  });

  it("changes frame only after 100 ms at rest on another stretch, never on the way past", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(700);
    rest(250); // into the change stretch
    vi.advanceTimersByTime(50);
    rest(100); // and back before the swap
    vi.advanceTimersByTime(200);
    expect(view()?.index).toBe(0);
    rest(250);
    vi.advanceTimersByTime(99);
    expect(view()?.index).toBe(0);
    vi.advanceTimersByTime(1);
    expect(view()?.index).toBe(1);
  });

  it("follows the pointer while it waits", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(700);
    tapestryThumb.move("s1", frames, 110, 420);
    expect(view()?.clientX).toBe(420);
  });

  it("closes 300 ms after leaving, and stays open across a quick move to the next timeline", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(700);
    tapestryThumb.leave();
    vi.advanceTimersByTime(250);
    tapestryThumb.enter(); // the next session's lane, within the grace
    rest(500, "s2");
    vi.advanceTimersByTime(100);
    expect(view()?.sessionId).toBe("s2");
    tapestryThumb.leave();
    vi.advanceTimersByTime(300);
    expect(view()).toBeNull();
  });

  it("reopens at once within a second of closing, and waits again after that", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(700);
    tapestryThumb.leave();
    vi.advanceTimersByTime(300);
    expect(view()).toBeNull();
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(0);
    expect(view()?.index).toBe(0);
    tapestryThumb.leave();
    vi.advanceTimersByTime(300 + 1000);
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(600);
    expect(view()).toBeNull();
  });

  it("shows frames that arrive while it is open", () => {
    tapestryThumb.enter();
    tapestryThumb.move("s1", null, 250, 300); // still loading
    vi.advanceTimersByTime(700);
    expect(view()).toBeNull();
    tapestryThumb.frames("s1", frames);
    expect(view()?.index).toBe(1);
  });

  it("names the change for a click only while a change frame shows", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(700);
    expect(tapestryThumb.changeAt("s1")).toBeNull(); // the turn's own frame
    rest(250);
    vi.advanceTimersByTime(100);
    expect(tapestryThumb.changeAt("s1")).toBe(200);
    expect(tapestryThumb.changeAt("s2")).toBeNull();
    tapestryThumb.leave();
    vi.advanceTimersByTime(300);
    expect(tapestryThumb.changeAt("s1")).toBeNull();
  });

  it("does not count a lane crossed on the way past as a close (the next lane still waits)", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(200);
    tapestryThumb.leave(); // never opened
    vi.advanceTimersByTime(300);
    tapestryThumb.enter();
    rest(100, "s2");
    vi.advanceTimersByTime(600);
    expect(view()).toBeNull();
    vi.advanceTimersByTime(100);
    expect(view()?.sessionId).toBe("s2");
  });

  it("still swaps after leaving and coming back to the new stretch within the grace", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(700);
    rest(250); // a swap to the change stretch is due…
    tapestryThumb.leave(); // …the pointer slips off the lane…
    vi.advanceTimersByTime(100);
    tapestryThumb.enter(); // …and comes back to the same stretch
    rest(260);
    vi.advanceTimersByTime(100);
    expect(view()?.index).toBe(1);
  });

  it("is forgotten with its slice", () => {
    tapestryThumb.enter();
    rest(100);
    vi.advanceTimersByTime(700);
    tapestryThumb.forget("s1");
    expect(view()).toBeNull();
  });
});

describe("framesFor", () => {
  it("fetches once per session and key, and hands the frames to an open preview", async () => {
    vi.mocked(apiGet).mockResolvedValue({ key: "k1", frames });
    expect(framesFor("s1", "k1")).toBeNull();
    expect(framesFor("s1", "k1")).toBeNull(); // in flight: no second fetch
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(apiGet).toHaveBeenCalledWith("/sessions/s1/turn-frames");
    await vi.waitFor(() => expect(framesFor("s1", "k1")).toBe(frames));
    expect(framesFor("s1", null)).toBeNull();
  });

  it("never fetches in an exported report, which carries no participant screens", () => {
    vi.mocked(isExportMode).mockReturnValueOnce(true);
    vi.mocked(apiGet).mockClear();
    expect(framesFor("s9", "k1")).toBeNull();
    expect(apiGet).not.toHaveBeenCalled();
  });

  it("hands arriving frames to a preview already open on the session", async () => {
    vi.mocked(apiGet).mockResolvedValue({ key: "k1", frames });
    tapestryThumb.enter();
    tapestryThumb.move("s3", framesFor("s3", "k1"), 250, 300);
    vi.advanceTimersByTime(700);
    expect(view()).toBeNull(); // open, and nothing to show yet
    await vi.waitFor(() => expect(view()?.index).toBe(1));
  });

  it("does not ask again after a failure until the key changes", async () => {
    vi.mocked(apiGet).mockClear();
    vi.mocked(apiGet).mockRejectedValue(new Error("404"));
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    framesFor("s4", "k1");
    await vi.waitFor(() => expect(warn).toHaveBeenCalled());
    framesFor("s4", "k1");
    framesFor("s4", "k1");
    expect(apiGet).toHaveBeenCalledTimes(1);
    framesFor("s4", "k2");
    expect(apiGet).toHaveBeenCalledTimes(2);
    warn.mockRestore();
  });

  it("does not show frames taken for other turns than the slice draws", async () => {
    vi.mocked(apiGet).mockClear();
    vi.mocked(apiGet).mockResolvedValue({ key: "newer", frames });
    tapestryThumb.enter();
    tapestryThumb.move("s5", framesFor("s5", "older"), 250, 300);
    vi.advanceTimersByTime(700);
    await vi.advanceTimersByTimeAsync(10); // the fetch settles
    expect(view()).toBeNull();
    expect(framesFor("s5", "older")).toBeNull(); // and is not asked for again
    expect(apiGet).toHaveBeenCalledTimes(1);
  });
});
