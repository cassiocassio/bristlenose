/**
 * The playback store: reconcile, pacing on the clock, what the views may show, the chip's
 * bounded wait, a hidden window, an export, and a researcher's own decision.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import type { LiveProposalsResponse, ProposedTagResponse, CodebookResponse } from "../utils/types";

vi.mock("../utils/exportData", () => ({ isExportMode: vi.fn(() => false), resolveFromExport: vi.fn() }));
vi.mock("../utils/api", () => ({
  getAutoCodeLive: vi.fn(),
  acceptProposal: vi.fn(() => Promise.resolve()),
  denyProposal: vi.fn(() => Promise.resolve()),
  toastSaveFailed: vi.fn(),
  // QuotesContext's imports, unused here.
  patchHidden: vi.fn(),
  patchStarred: vi.fn(),
  patchEdits: vi.fn(),
  patchQuoteBreaks: vi.fn(),
  patchTags: vi.fn(),
  patchDeletedBadges: vi.fn(),
}));

import { acceptProposal, denyProposal, getAutoCodeLive, toastSaveFailed } from "../utils/api";
import { isExportMode } from "../utils/exportData";
import {
  CALM_MS,
  CHIP_WAIT_MS,
  FLASH_MS,
  HANDOVER_GRACE_MS,
  LIVE_POLL_MS,
  PULSE_AFTER_MS,
  acceptLiveProposal,
  applyLiveCounts,
  beginHandover,
  denyLiveProposal,
  followAutoCode,
  getPlaybackSnapshot,
  holdForPlayback,
  playbackPending,
  removeLiveAccepted,
  resetPlayback,
  restoreScrollAnchor,
  snapshotHasRun,
  stampedRead,
  whenPlayedOut,
  _queuedForTest,
} from "./AutoCodePlayback";
import { getQuotesSnapshot, resetStore } from "./QuotesContext";
import { mergedProposals, mergedTags } from "../utils/liveTags";

const live = vi.mocked(getAutoCodeLive);

function prop(id: number, over: Partial<ProposedTagResponse> = {}): ProposedTagResponse {
  return {
    id,
    quote_id: 1000 + id,
    dom_id: `q-p1-${id}`,
    session_id: "s1",
    speaker_code: "p1",
    start_timecode: id,
    quote_text: "text",
    tag_definition_id: 50 + (id % 3),
    tag_name: `tag${50 + (id % 3)}`,
    group_name: "G",
    colour_set: "ux",
    colour_index: 0,
    confidence: 0.6,
    rationale: "",
    status: "pending",
    decided_by: null,
    ...over,
  };
}

/** A live read answering `rows` in full and `states` for every row the run holds. */
function answer(
  rows: ProposedTagResponse[],
  all: ProposedTagResponse[],
  run: Partial<LiveProposalsResponse["run"]> = {},
): LiveProposalsResponse {
  return {
    proposals: rows,
    total: rows.length,
    states: all.map((p) => ({
      id: p.id, quote_id: p.quote_id, tag_definition_id: p.tag_definition_id,
      status: p.status, decided_by: p.decided_by,
    })),
    run: {
      status: "running", ending: true, settled: false,
      cursor: rows.length ? Math.max(...rows.map((r) => r.id)) : null,
      ...run,
    },
  };
}

const overlay = () => getQuotesSnapshot().live;
const shownIds = () =>
  Object.values(overlay().byQuote).flat().map((t) => `${t.id}:${t.shown}`).sort();

/** Let a read answer and the clock run. */
async function advance(ms: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(ms);
}

let tagsChanged: Mock<() => void>;
let codebookChanged: Mock<() => void>;

beforeEach(() => {
  vi.useFakeTimers();
  resetStore();
  resetPlayback();
  vi.clearAllMocks();
  vi.mocked(isExportMode).mockReturnValue(false);
  Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
  tagsChanged = vi.fn<() => void>();
  codebookChanged = vi.fn<() => void>();
  document.addEventListener("bn:tags-changed", tagsChanged);
  window.addEventListener("codebook-changed", codebookChanged);
});

afterEach(() => {
  document.removeEventListener("bn:tags-changed", tagsChanged);
  window.removeEventListener("codebook-changed", codebookChanged);
  resetPlayback();
  vi.useRealTimers();
});

describe("a page opened mid-run", () => {
  it("shows what is already saved at once, without flashing it", async () => {
    const saved = [prop(1), prop(2, { status: "accepted", decided_by: "threshold" })];
    live.mockResolvedValueOnce(answer(saved, saved));
    followAutoCode("uxr", "first");
    await advance(0);
    expect(shownIds()).toEqual(["1:tentative", "2:accepted"]);
    expect(Object.values(overlay().byQuote).flat().some((t) => t.flash)).toBe(false);
    expect(_queuedForTest()).toBe(0);
    // The first read asks for everything.
    expect(live).toHaveBeenCalledWith("uxr", null);
  });
});

describe("reconcile", () => {
  it("follows the cursor, and takes decisions on rows it holds from the states alone", async () => {
    const a = prop(1);
    live.mockResolvedValueOnce(answer([a], [a]));
    followAutoCode("uxr", "first");
    await advance(0);
    // The next read: nothing new, but row 1 was accepted live (a states-only change).
    const accepted = { ...a, status: "accepted" as const, decided_by: "threshold" as const };
    live.mockResolvedValueOnce(answer([], [accepted], { cursor: 1 }));
    await advance(LIVE_POLL_MS);
    expect(live).toHaveBeenLastCalledWith("uxr", 1);
    // Queued, not shown yet: still tentative on every view.
    expect(shownIds()).toEqual(["1:tentative"]);
    expect(overlay().waitingAccept.has("q-p1-1|tag51")).toBe(true);
    await advance(3000);
    expect(shownIds()).toEqual(["1:accepted"]);
  });

  it("fetches in full when an id comes back for another quote or tag (SQLite reuses ids)", async () => {
    const a = prop(1);
    live.mockResolvedValueOnce(answer([a], [a]));
    followAutoCode("uxr", "first");
    await advance(0);
    const reused = prop(1, { quote_id: 9999, dom_id: "q-p9-1" });
    live.mockResolvedValueOnce(answer([], [reused], { cursor: 1 }));
    await advance(LIVE_POLL_MS);
    // The old row is gone at once; the next read asks for everything.
    expect(shownIds()).toEqual([]);
    live.mockResolvedValueOnce(answer([reused], [reused], { cursor: 1 }));
    await advance(LIVE_POLL_MS);
    expect(live).toHaveBeenLastCalledWith("uxr", null);
    await advance(3000);
    expect(Object.keys(overlay().byQuote)).toEqual(["q-p9-1"]);
  });

  it("fetches in full when a state at or below the cursor has no row", async () => {
    const a = prop(1);
    const b = prop(2);
    live.mockResolvedValueOnce(answer([b], [a, b], { cursor: 2 }));
    followAutoCode("uxr", "first");
    await advance(0);
    live.mockResolvedValueOnce(answer([a, b], [a, b], { cursor: 2 }));
    await advance(LIVE_POLL_MS);
    expect(live).toHaveBeenLastCalledWith("uxr", null);
  });

  it("drops a held row with no state", async () => {
    const a = prop(1);
    const b = prop(2);
    live.mockResolvedValueOnce(answer([a, b], [a, b]));
    followAutoCode("uxr", "first");
    await advance(0);
    live.mockResolvedValueOnce(answer([], [b], { cursor: 2 }));
    await advance(LIVE_POLL_MS);
    expect(shownIds()).toEqual(["2:tentative"]);
  });

  it("stops reading after the first settled read", async () => {
    live.mockResolvedValueOnce(answer([], [], { settled: true, status: "completed", ending: false }));
    followAutoCode("uxr", "first");
    await advance(LIVE_POLL_MS * 5);
    expect(live).toHaveBeenCalledTimes(1);
  });
});

describe("never shown before it is played", () => {
  it("holds a new row back from the cards, the counts and the flashes until it lands", async () => {
    live.mockResolvedValueOnce(answer([], []));
    followAutoCode("uxr", "first");
    await advance(0);
    const rows = [prop(1), prop(2, { status: "accepted", decided_by: "threshold" })];
    live.mockResolvedValueOnce(answer(rows, rows));
    await advance(LIVE_POLL_MS);

    // Held, not landed: no card draws it, even where the store already has it (a refetch).
    expect(overlay().held.has(1)).toBe(true);
    expect(overlay().byQuote["q-p1-1"]).toBeUndefined();
    const storeProposal = { id: 1, tag_name: "tag51", group_name: "G", colour_set: "ux", colour_index: 0, confidence: 0.6, rationale: "" };
    expect(mergedProposals("q-p1-1", [storeProposal], [], overlay())).toEqual([]);
    const storeTag = { name: "tag52", codebook_group: "G", colour_set: "ux", colour_index: 0 };
    expect(mergedTags("q-p1-2", [storeTag], overlay())).toEqual([]);
    // No count, no flash on the Codebook lens or the sidebar.
    const cb = codebookWith(51, 52);
    const counted = applyLiveCounts(cb, getPlaybackSnapshot())!;
    expect(counted.groups[0].tags.map((t) => [t.tentative_count, t.count])).toEqual([[0, 0], [0, 0]]);
    expect(getPlaybackSnapshot().flashingTagIds.size).toBe(0);

    // Played: every view at once.
    await advance(4000);
    expect(shownIds()).toEqual(["1:tentative", "2:accepted"]);
    const after = applyLiveCounts(cb, getPlaybackSnapshot())!;
    expect(after.groups[0].tags.map((t) => [t.tentative_count, t.count])).toEqual([[1, 0], [0, 1]]);
  });

  it("flashes an accepted landing on the card, the sidebar and the lens, then stops", async () => {
    live.mockResolvedValueOnce(answer([], []));
    followAutoCode("uxr", "first");
    await advance(0);
    const row = prop(2, { status: "accepted", decided_by: "threshold" });
    live.mockResolvedValueOnce(answer([row], [row], { settled: true, status: "completed", ending: false }));
    await advance(LIVE_POLL_MS);
    let seen = false;
    for (let i = 0; i < 40 && !seen; i++) {
      await advance(50);
      seen = getPlaybackSnapshot().flashingTagIds.has(52);
    }
    expect(seen).toBe(true);
    expect(getPlaybackSnapshot().flashingTagNames.has("tag52")).toBe(true);
    expect(overlay().byQuote["q-p1-2"][0].flash).toBe(true);
    await advance(FLASH_MS + 100);
    expect(getPlaybackSnapshot().flashingTagIds.size).toBe(0);
    expect(overlay().byQuote["q-p1-2"][0].flash).toBe(false);
  });
});

function codebookWith(...tagIds: number[]): CodebookResponse {
  return {
    groups: [{
      id: 1, name: "G", subtitle: "", colour_set: "ux", order: 0, is_default: false,
      framework_id: "uxr", total_quotes: 0,
      tags: tagIds.map((id, i) => ({ id, name: `tag${id}`, count: 0, tentative_count: 0, colour_index: i })),
    }],
    ungrouped: [],
    all_tag_names: [],
  } as unknown as CodebookResponse;
}

/** Times (ms) at which the overlay changed what it shows. */
async function landingTimes(totalMs: number): Promise<number[]> {
  const times: number[] = [];
  let last = getPlaybackSnapshot().landings;
  const t0 = Date.now();
  for (let t = 0; t < totalMs; t += 50) {
    await advance(50);
    const now = getPlaybackSnapshot().landings;
    if (now !== last) times.push(Date.now() - t0);
    last = now;
  }
  return times;
}

function maxInAnySecond(times: number[]): number {
  let max = 0;
  for (let i = 0; i < times.length; i++) {
    let n = 0;
    for (let j = i; j < times.length && times[j] <= times[i] + 1000; j++) n++;
    max = Math.max(max, n);
  }
  return max;
}

describe("pacing on the clock", () => {
  it("lands a big batch no faster than three times a second while the run goes on", async () => {
    live.mockResolvedValueOnce(answer([], []));
    followAutoCode("uxr", "first");
    await advance(0);
    const rows = Array.from({ length: 60 }, (_, i) => prop(i + 1));
    live.mockResolvedValue(answer(rows, rows));
    const times = await landingTimes(20_000);
    expect(times.length).toBeGreaterThan(10);
    expect(maxInAnySecond(times)).toBeLessThanOrEqual(3);
  });

  it("plays the end-of-run top-up out in a second and a half, at most three landings a second", async () => {
    const rows = Array.from({ length: 30 }, (_, i) => prop(i + 1));
    live.mockResolvedValueOnce(answer(rows, rows));
    followAutoCode("uxr", "first");
    await advance(0);
    // The top-up: every row accepted at once, and the run settled.
    const topped = rows.map((r) => ({ ...r, status: "accepted" as const, decided_by: "threshold" as const }));
    live.mockResolvedValueOnce(answer([], topped, { settled: true, status: "completed", ending: false, cursor: 30 }));
    const times = await landingTimes(LIVE_POLL_MS + 3000);
    expect(shownIds().every((s) => s.endsWith(":accepted"))).toBe(true);
    expect(times.length).toBeLessThanOrEqual(5);
    expect(times[times.length - 1] - times[0]).toBeLessThanOrEqual(1500);
    expect(maxInAnySecond(times)).toBeLessThanOrEqual(3);
  });

  it("lands at once, unflashed, under reduced motion", async () => {
    const mm = vi.fn(() => ({ matches: true }));
    vi.stubGlobal("matchMedia", mm);
    try {
      live.mockResolvedValueOnce(answer([], []));
      followAutoCode("uxr", "first");
      await advance(0);
      const rows = Array.from({ length: 20 }, (_, i) => prop(i + 1, { status: "accepted", decided_by: "threshold" }));
      live.mockResolvedValueOnce(answer(rows, rows));
      await advance(LIVE_POLL_MS + 100);
      expect(shownIds()).toHaveLength(20);
      expect(getPlaybackSnapshot().flashingTagIds.size).toBe(0);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("a hidden window", () => {
  it("pauses, then catches up quickly when shown", async () => {
    live.mockResolvedValueOnce(answer([], []));
    followAutoCode("uxr", "first");
    await advance(0);
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    const rows = Array.from({ length: 12 }, (_, i) => prop(i + 1));
    live.mockResolvedValue(answer(rows, rows));
    await advance(10_000);
    expect(shownIds()).toHaveLength(0);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    const times = await landingTimes(2000);
    expect(shownIds()).toHaveLength(12);
    expect(times[times.length - 1]).toBeLessThanOrEqual(1600);
    expect(maxInAnySecond(times)).toBeLessThanOrEqual(3);
  });
});

describe("an exported report", () => {
  it("follows nothing: no read, no overlay, the embedded data as it is", async () => {
    vi.mocked(isExportMode).mockReturnValue(true);
    followAutoCode("uxr", "first");
    await advance(LIVE_POLL_MS * 3);
    expect(live).not.toHaveBeenCalled();
    expect(overlay().held.size).toBe(0);
    const cb = codebookWith(51);
    expect(applyLiveCounts(cb, getPlaybackSnapshot())).toBe(cb);
    expect(document.documentElement.hasAttribute("data-autocode-tentative")).toBe(false);
  });
});

describe("the chip waits for the last tag (D11), within a bound", () => {
  it("holds while the run lands, ends once it has, and never past the bound", async () => {
    const rows = [prop(1)];
    live.mockResolvedValueOnce(answer(rows, rows));
    followAutoCode("uxr", "first");
    await advance(0);
    // Not settled: the chip keeps running.
    live.mockResolvedValue(answer([], rows, { cursor: 1 }));
    expect(playbackPending("uxr")).toBe(true);
    // A run that never settles on this page: the bound ends the wait.
    await advance(CHIP_WAIT_MS);
    expect(playbackPending("uxr")).toBe(false);
  });

  it("ends as soon as the settled run's queue is played out", async () => {
    live.mockResolvedValueOnce(answer([], []));
    followAutoCode("uxr", "first");
    await advance(0);
    const rows = [prop(1, { status: "accepted", decided_by: "threshold" })];
    live.mockResolvedValueOnce(answer(rows, rows, { settled: true, status: "completed", ending: false }));
    await advance(LIVE_POLL_MS);
    expect(playbackPending("uxr")).toBe(true);
    await advance(2000);
    expect(playbackPending("uxr")).toBe(false);
  });

  it("never waits in a hidden window, nor before a first read, nor after the reads failed", async () => {
    live.mockReturnValueOnce(new Promise(() => {}));
    followAutoCode("uxr", "first");
    expect(playbackPending("uxr")).toBe(false);
    resetPlayback();
    live.mockReset();
    live.mockResolvedValueOnce(answer([prop(1)], [prop(1)]));
    followAutoCode("uxr", "first");
    await advance(0);
    // Visible, it waits (the run is still landing)…
    expect([live.mock.calls.length, shownIds()]).toEqual([1, ["1:tentative"]]);
    expect(playbackPending("uxr")).toBe(true);
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    expect(playbackPending("uxr")).toBe(false);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    live.mockRejectedValue(new Error("down"));
    await advance(LIVE_POLL_MS * 6);
    expect(playbackPending("uxr")).toBe(false);
  });

  it("holds a finished chip at running, with the server's count, and lets every other status by", async () => {
    live.mockResolvedValueOnce(answer([prop(1)], [prop(1)]));
    live.mockResolvedValue(answer([], [prop(1)], { cursor: 1 }));
    followAutoCode("uxr", "first");
    await advance(0);
    const done = {
      status: "completed" as const, progressLabel: null, durationLabel: "1:00",
      errorMessage: null, partialMessage: null, hasProposals: true,
    };
    const status = { processed_quotes: 40, total_quotes: 40 } as never;
    expect(holdForPlayback("uxr", done, status)).toMatchObject({ status: "running", progressLabel: "40/40" });
    const failed = { ...done, status: "failed" as const };
    expect(holdForPlayback("uxr", failed, status)).toBe(failed);
    // Another codebook, not followed here: done as the server says.
    expect(holdForPlayback("norman", done, status)).toBe(done);
    await advance(CHIP_WAIT_MS);
    expect(holdForPlayback("uxr", done, status)).toBe(done);
  });

  it("whenPlayedOut resolves within its limit even when nothing settles", async () => {
    live.mockResolvedValueOnce(answer([prop(1)], [prop(1)]));
    live.mockResolvedValue(answer([], [prop(1)], { cursor: 1 }));
    followAutoCode("uxr", "first");
    await advance(0);
    let done = false;
    void whenPlayedOut("uxr", 5000).then(() => { done = true; });
    await advance(4000);
    expect(done).toBe(false);
    await advance(1500);
    expect(done).toBe(true);
  });
});

describe("a researcher's own decision", () => {
  it("accepting a tag waiting in the queue shows at once, never behind the playback", async () => {
    live.mockResolvedValueOnce(answer([prop(1)], [prop(1)]));
    followAutoCode("uxr", "first");
    await advance(0);
    const rows = Array.from({ length: 30 }, (_, i) => prop(i + 2));
    const all = [prop(1), ...rows];
    live.mockResolvedValue(answer(rows, all, { cursor: 31 }));
    await advance(LIVE_POLL_MS);
    expect(_queuedForTest()).toBeGreaterThan(20);
    acceptLiveProposal(1);
    expect(shownIds()).toContain("1:accepted");
    expect(acceptProposal).toHaveBeenCalledWith(1);
    // The server still says pending on the next read: the decision holds.
    await advance(LIVE_POLL_MS);
    expect(shownIds()).toContain("1:accepted");
  });

  it("a tag waiting in the queue the researcher accepts lands at once", async () => {
    live.mockResolvedValueOnce(answer([], []));
    followAutoCode("uxr", "first");
    await advance(0);
    const rows = Array.from({ length: 30 }, (_, i) => prop(i + 1));
    live.mockResolvedValue(answer(rows, rows, { cursor: 30 }));
    await advance(LIVE_POLL_MS);
    acceptLiveProposal(30);
    expect(shownIds()).toContain("30:accepted");
    expect(_queuedForTest()).toBe(29);
  });

  it("puts a failed accept back and says so", async () => {
    vi.mocked(acceptProposal).mockRejectedValueOnce({ status: 500 });
    live.mockResolvedValueOnce(answer([prop(1)], [prop(1)]));
    followAutoCode("uxr", "first");
    await advance(0);
    acceptLiveProposal(1);
    await advance(0);
    expect(shownIds()).toEqual(["1:tentative"]);
    expect(toastSaveFailed).toHaveBeenCalled();
  });

  it("a deny takes the tag off at once; removing a landed accepted tag overrides its acceptance", async () => {
    const rows = [prop(1), prop(2, { status: "accepted", decided_by: "threshold" })];
    live.mockResolvedValueOnce(answer(rows, rows));
    followAutoCode("uxr", "first");
    await advance(0);
    denyLiveProposal(1);
    removeLiveAccepted(2);
    expect(shownIds()).toEqual([]);
    expect(denyProposal).toHaveBeenCalledWith(1);
    expect(denyProposal).toHaveBeenCalledWith(2, "accepted");
  });
});

describe("the run's end", () => {
  it("fires no bn:tags-changed or codebook-changed of its own, batch after batch", async () => {
    live.mockResolvedValueOnce(answer([], []));
    followAutoCode("uxr", "first");
    await advance(0);
    for (let b = 1; b <= 5; b++) {
      const rows = Array.from({ length: b * 5 }, (_, i) => prop(i + 1));
      live.mockResolvedValueOnce(answer(rows.slice((b - 1) * 5), rows, { cursor: (b - 1) * 5 }));
      await advance(LIVE_POLL_MS);
    }
    await advance(10_000);
    expect(tagsChanged).not.toHaveBeenCalled();
    expect(codebookChanged).not.toHaveBeenCalled();
  });

  it("hands over: data read after the handover has the run in it, and the overlay then goes", async () => {
    const rows = [prop(1)];
    live.mockResolvedValueOnce(answer(rows, rows, { settled: true, status: "completed", ending: false }));
    followAutoCode("uxr", "first");
    await advance(0);
    const before = await stampedRead(() => Promise.resolve(codebookWith(51)));
    await advance(1);
    beginHandover("uxr");
    const after = await stampedRead(() => Promise.resolve(codebookWith(51)));
    const fw = getPlaybackSnapshot().frameworks.get("uxr")!;
    expect(snapshotHasRun(before, fw)).toBe(false);
    expect(snapshotHasRun(after, fw)).toBe(true);
    // The older read still gets the playback's counts; the newer one is left as it is.
    expect(applyLiveCounts(before, getPlaybackSnapshot())!.groups[0].tags[0].tentative_count).toBe(1);
    expect(applyLiveCounts(after, getPlaybackSnapshot())).toBe(after);
    await advance(HANDOVER_GRACE_MS + 100);
    expect(overlay().held.size).toBe(0);
    expect(getPlaybackSnapshot().frameworks.size).toBe(0);
  });
});

describe("D8: the pulse schedule", () => {
  it("pulses while a run lands and for a minute after, calms for 30 s, then is still", async () => {
    const root = document.documentElement;
    expect(root.hasAttribute("data-autocode-tentative")).toBe(false);
    const rows = [prop(1)];
    live.mockResolvedValueOnce(answer(rows, rows));
    followAutoCode("uxr", "first");
    await advance(0);
    expect(root.getAttribute("data-autocode-tentative")).toBe("pulse");
    live.mockResolvedValueOnce(answer([], rows, { settled: true, status: "completed", ending: false, cursor: 1 }));
    await advance(LIVE_POLL_MS + 100);
    expect(root.getAttribute("data-autocode-tentative")).toBe("pulse");
    await advance(PULSE_AFTER_MS);
    expect(root.getAttribute("data-autocode-tentative")).toBe("calm");
    await advance(CALM_MS);
    expect(root.hasAttribute("data-autocode-tentative")).toBe(false);
  });
});

describe("holding the reading position (WebKit)", () => {
  it("scrolls back by however far the top card moved when a landing grew the page above it", async () => {
    vi.stubGlobal("CSS", { supports: () => false });
    Object.defineProperty(window, "scrollY", { value: 400, configurable: true });
    const scrollBy = vi.spyOn(window, "scrollBy").mockImplementation(() => {});
    const cards = [0, 1, 2].map(() => {
      const el = document.createElement("blockquote");
      el.className = "quote-card";
      document.body.appendChild(el);
      return el;
    });
    let shift = 0;
    cards.forEach((el, i) => {
      el.getBoundingClientRect = () => ({ top: -300 + i * 200 + shift, bottom: -100 + i * 200 + shift } as DOMRect);
    });
    try {
      live.mockResolvedValueOnce(answer([], []));
      followAutoCode("uxr", "first");
      await advance(0);
      live.mockResolvedValueOnce(answer([prop(1)], [prop(1)]));
      // The read lands its row on the next landing; the card above grows by 24 px as it does.
      await advance(LIVE_POLL_MS);
      shift = 24;
      restoreScrollAnchor();
      expect(scrollBy).toHaveBeenCalledWith(0, 24);
    } finally {
      cards.forEach((el) => el.remove());
      scrollBy.mockRestore();
      vi.unstubAllGlobals();
      Object.defineProperty(window, "scrollY", { value: 0, configurable: true });
    }
  });
});
