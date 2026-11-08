import { describe, expect, it } from "vitest";
import boardFixture from "../../tests/fixtures/figjam-board-v1.json";
import { parseBoard } from "../../figjam-plugin/src/board";
import { type BoardApi, draw, isTransient, NOT_CONNECTED, RETRY_DELAYS_MS, Stopped } from "./draw";
import { planBoard } from "./layout";

const BOARD_FILE = JSON.stringify(boardFixture);

interface Call {
  kind: string;
  props: Record<string, unknown>;
}

function fakeBoard(opts: { failFirstSticky?: number; failWith?: string; space?: { x: number; y: number } } = {}) {
  const calls: Call[] = [];
  let id = 0;
  let stickyFailures = opts.failFirstSticky ?? 0;
  const item = (kind: string, props: Record<string, unknown>) => {
    calls.push({ kind, props });
    return Promise.resolve({ id: `${kind}-${++id}` });
  };
  const board: BoardApi = {
    createFrame: (p) => item("frame", p),
    createText: (p) => item("text", p),
    createStickyNote: (p) => {
      if (stickyFailures > 0) {
        stickyFailures--;
        calls.push({ kind: "refused", props: p });
        return Promise.reject(new Error(opts.failWith ?? "rate limited"));
      }
      return item("sticky", p);
    },
    group: (p) => item("group", { items: p.items }),
    findEmptySpace: (p) => {
      calls.push({ kind: "space", props: { ...p } });
      return Promise.resolve({ x: opts.space?.x ?? 1000, y: opts.space?.y ?? 2000, width: p.width, height: p.height });
    },
    viewport: {
      get: () => Promise.resolve({ x: 0, y: 0, width: 800, height: 600 }),
      zoomTo: (items) => {
        calls.push({ kind: "zoom", props: { count: Array.isArray(items) ? items.length : 1 } });
        return Promise.resolve();
      },
    },
  };
  return { board, calls };
}

const noSleep = () => Promise.resolve();

describe("drawing a board", () => {
  it("makes the frames, the title, every sticky in order, groups the split quotes, then zooms", async () => {
    const plan = planBoard(parseBoard(BOARD_FILE));
    const { board, calls } = fakeBoard();
    const tally = { built: 0 };
    const seen: number[] = [];
    await draw(board, plan, tally, { progress: (d) => seen.push(d), sleep: noSleep });

    const kinds = calls.map((c) => c.kind);
    expect(kinds.filter((k) => k === "frame")).toHaveLength(plan.frames.length);
    expect(kinds.filter((k) => k === "sticky")).toHaveLength(plan.stickies.length);
    expect(kinds.indexOf("text")).toBeGreaterThan(kinds.lastIndexOf("frame"));
    expect(kinds[kinds.length - 1]).toBe("zoom");
    // One group per split quote (the fixture has a pair and a trio), each made after its parts.
    const groups = calls.filter((c) => c.kind === "group");
    expect(groups.map((g) => (g.props.items as object[]).length)).toEqual([2, 3]);
    expect(tally.built).toBe(plan.expectedQuotes);
    expect(seen[0]).toBe(0);
    expect(seen[seen.length - 1]).toBe(plan.expectedQuotes);
  });

  it("places the board in the free space Miro found, as centres", async () => {
    const plan = planBoard(parseBoard(BOARD_FILE));
    const { board, calls } = fakeBoard({ space: { x: 5000, y: -3000 } });
    await draw(board, plan, { built: 0 }, { progress: () => {}, sleep: noSleep });
    const ox = 5000 - plan.width / 2;
    const oy = -3000 - plan.height / 2;
    const first = calls.find((c) => c.kind === "sticky")!.props;
    const s = plan.stickies[0];
    expect(first.x).toBeCloseTo(ox + s.x + s.width / 2, 6);
    expect(first.y).toBeCloseTo(oy + s.y + s.height / 2, 6);
    expect(first.width).toBe(s.width);
    expect(first).not.toHaveProperty("height"); // Miro takes one of the two and keeps the proportion
    expect(first.shape).toBe(plan.shape);
    const frame = calls.find((c) => c.kind === "frame")!.props;
    expect(frame.x).toBeCloseTo(ox + plan.frames[0].x + plan.frames[0].width / 2, 6);
    const space = calls.find((c) => c.kind === "space")!.props;
    expect([space.width, space.height]).toEqual([plan.width, plan.height]);
  });

  it("tries a refused call again after a pause, and carries on", async () => {
    const plan = planBoard(parseBoard(BOARD_FILE));
    const { board, calls } = fakeBoard({ failFirstSticky: 2 });
    const waits: number[] = [];
    await draw(board, plan, { built: 0 }, { progress: () => {}, sleep: (ms) => (waits.push(ms), Promise.resolve()) });
    expect(waits).toEqual(RETRY_DELAYS_MS);
    expect(calls.filter((c) => c.kind === "sticky")).toHaveLength(plan.stickies.length);
  });

  it("gives up after the last retry and says how far it got", async () => {
    const plan = planBoard(parseBoard(BOARD_FILE));
    const { board, calls } = fakeBoard({ failFirstSticky: 99 });
    const tally = { built: 0 };
    await expect(draw(board, plan, tally, { progress: () => {}, sleep: noSleep })).rejects.toThrow("rate limited");
    expect(tally.built).toBe(0);
    expect(calls[calls.length - 1].kind).toBe("zoom"); // the frames already drawn are shown
  });

  it("says a refusal that isn't a rate limit at once, without retrying", async () => {
    const plan = planBoard(parseBoard(BOARD_FILE));
    const { board } = fakeBoard({ failFirstSticky: 99, failWith: "Miro SDK is not connected" });
    const waits: number[] = [];
    await expect(
      draw(board, plan, { built: 0 }, { progress: () => {}, sleep: (ms) => (waits.push(ms), Promise.resolve()) }),
    ).rejects.toThrow("not connected");
    expect(waits).toEqual([]);
  });

  it("honours Stop instead of waiting out a rate limit", async () => {
    const plan = planBoard(parseBoard(BOARD_FILE));
    const { board } = fakeBoard({ failFirstSticky: 1 });
    const waits: number[] = [];
    await expect(
      draw(board, plan, { built: 0 }, { progress: () => {}, sleep: (ms) => (waits.push(ms), Promise.resolve()), stopRequested: () => true }),
    ).rejects.toBeInstanceOf(Stopped);
    expect(waits).toEqual([]);
  });

  it("says Miro isn't answering instead of waiting forever when the SDK never connects", async () => {
    const plan = planBoard(parseBoard(BOARD_FILE));
    const { board, calls } = fakeBoard();
    board.viewport.get = () => new Promise(() => {}); // what Miro's loader does when it can't connect
    await expect(
      draw(board, plan, { built: 0 }, { progress: () => {}, sleep: noSleep, firstAnswerMs: 20 }),
    ).rejects.toThrow(NOT_CONNECTED);
    expect(calls.filter((c) => c.kind === "sticky")).toHaveLength(0);
    expect(isTransient(new Error(NOT_CONNECTED))).toBe(false); // said at once, not retried
  });

  it("tells transient refusals from the rest", () => {
    expect(isTransient(new Error("Rate limit exceeded"))).toBe(true);
    expect(isTransient(new Error("Request timed out"))).toBe(true);
    expect(isTransient(new Error("Miro SDK is not connected"))).toBe(false);
    expect(isTransient(new Error("Invalid parameter: content"))).toBe(false);
  });

  it("stops between quotes when asked, keeping what was drawn", async () => {
    const plan = planBoard(parseBoard(BOARD_FILE));
    const { board, calls } = fakeBoard();
    const tally = { built: 0 };
    let stopAfter = 3;
    await expect(
      draw(board, plan, tally, { progress: () => {}, sleep: noSleep, stopRequested: () => tally.built >= stopAfter }),
    ).rejects.toBeInstanceOf(Stopped);
    expect(tally.built).toBe(stopAfter);
    // Nothing after the third quote's last sticky was started (not even the next column's header).
    const throughThird = plan.stickies.findIndex((s) => s.quote === stopAfter - 1 && s.last) + 1;
    expect(calls.filter((c) => c.kind === "sticky")).toHaveLength(throughThird);
    expect(calls[calls.length - 1].kind).toBe("zoom");
    stopAfter = 0;
  });
});
