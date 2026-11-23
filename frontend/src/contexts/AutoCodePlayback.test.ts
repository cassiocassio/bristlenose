/**
 * The playback store: reconcile, pacing on the clock, what the views may show, the counts a
 * codebook read gains, the chip's bounded wait, the handover, a hidden window, an export, a
 * researcher's own decision, and how often the quotes store changes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";
import type {
  CodebookResponse,
  LiveProposalsResponse,
  ProposedTagResponse,
  QuoteResponse,
  TagResponse,
} from "../utils/types";

vi.mock("../utils/exportData", () => ({ isExportMode: vi.fn(() => false), resolveFromExport: vi.fn() }));
vi.mock("../utils/api", () => ({
  getAutoCodeLive: vi.fn(),
  acceptProposal: vi.fn(() => Promise.resolve()),
  denyProposal: vi.fn(() => Promise.resolve()),
  toastSaveFailed: vi.fn(),
  // QuotesContext's writes.
  patchHidden: vi.fn(() => Promise.resolve({})),
  patchStarred: vi.fn(() => Promise.resolve({})),
  patchEdits: vi.fn(() => Promise.resolve({})),
  patchQuoteBreaks: vi.fn(() => Promise.resolve({})),
  patchTags: vi.fn(() => Promise.resolve({})),
  patchDeletedBadges: vi.fn(() => Promise.resolve({})),
}));
// The real quotes store, with its one write from the playback counted.
vi.mock("./QuotesContext", async (importOriginal) => {
  const mod = await importOriginal<typeof import("./QuotesContext")>();
  return { ...mod, setLiveOverlay: vi.fn((l: Parameters<typeof mod.setLiveOverlay>[0]) => mod.setLiveOverlay(l)) };
});

import { acceptProposal, denyProposal, getAutoCodeLive, patchTags, toastSaveFailed } from "../utils/api";
import { isExportMode } from "../utils/exportData";
import {
  CALM_MS,
  CHIP_WAIT_MS,
  FLASH_MS,
  HANDOVER_GRACE_MS,
  LIVE_POLL_MS,
  PULSE_AFTER_MS,
  acceptLanding,
  beginHandover,
  denyLanding,
  followAutoCode,
  holdForPlayback,
  playbackPending,
  removeLanding,
  resetPlayback,
  serverFinished,
  whenPlayedOut,
  _queueForTest,
  _queuedForTest,
} from "./AutoCodePlayback";
import {
  applyLiveCounts,
  getPlaybackSnapshot,
  restoreScrollAnchor,
  snapshotHasRun,
  stampedRead,
} from "./AutoCodePlaybackView";
import { getQuotesSnapshot, initFromQuotes, removeTag, resetStore, setLiveOverlay } from "./QuotesContext";
import { mergedProposals, mergedTags, storeCarries } from "../utils/liveTags";
import type { LiveTag } from "../utils/liveTags";

const live = vi.mocked(getAutoCodeLive);
const overlayWrites = vi.mocked(setLiveOverlay);
const JOB = "autocode:uxr:1";

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

const accepted = (p: ProposedTagResponse): ProposedTagResponse =>
  ({ ...p, status: "accepted", decided_by: "threshold" });

/** A live read answering `rows` in full and `all`'s states. */
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
const SETTLED = { settled: true, status: "completed" as const, ending: false };

const overlay = () => getQuotesSnapshot().live;
const shownIds = () =>
  Object.values(overlay().byQuote).flat().map((t) => `${t.id}:${t.shown}`).sort();
const landedTag = (id: number): LiveTag => Object.values(overlay().byQuote).flat().find((t) => t.id === id)!;

async function advance(ms: number): Promise<void> {
  await vi.advanceTimersByTimeAsync(ms);
}

/** Start following with `first` as the first read's answer. */
async function start(first: LiveProposalsResponse, kind: "first" | "catchup" = "first", fw = "uxr", key = JOB) {
  live.mockResolvedValueOnce(first);
  followAutoCode(fw, kind, key);
  await advance(0);
}

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

function quote(domId: string, tags: TagResponse[] = [], proposed: { id: number; def: number }[] = []): QuoteResponse {
  return {
    dom_id: domId, text: "t", participant_id: "p1", session_id: "s1", start_timecode: 1,
    tags, deleted_badges: [], is_hidden: false, is_starred: false, edited_text: null,
    researcher_breaks: null, segment_index: 0,
    proposed_tags: proposed.map((p) => ({
      id: p.id, tag_definition_id: p.def, tag_name: `tag${p.def}`, group_name: "G",
      colour_set: "ux", colour_index: 0, confidence: 0.8, rationale: "",
    })),
  } as unknown as QuoteResponse;
}

const tagOf = (def: number, source = "autocode"): TagResponse =>
  ({ id: def, name: `tag${def}`, codebook_group: "G", colour_set: "ux", colour_index: 0, source });

/** Times (ms) at which the overlay changed what it shows. */
async function landingTimes(totalMs: number): Promise<number[]> {
  const times: number[] = [];
  let last = overlay();
  const t0 = Date.now();
  for (let t = 0; t < totalMs; t += 50) {
    await advance(50);
    if (overlay() !== last) times.push(Date.now() - t0);
    last = overlay();
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

let tagsChanged: Mock<() => void>;
let codebookChanged: Mock<() => void>;

beforeEach(() => {
  vi.useFakeTimers();
  resetStore();
  resetPlayback();
  vi.clearAllMocks();
  // Answers queued for one test are not left for the next.
  live.mockReset();
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
    const saved = [prop(1), accepted(prop(2))];
    await start(answer(saved, saved));
    expect(shownIds()).toEqual(["1:tentative", "2:accepted"]);
    expect(getPlaybackSnapshot().flashingCardKeys.size).toBe(0);
    expect(_queuedForTest()).toBe(0);
    expect(live).toHaveBeenCalledWith("uxr", null);
  });
});

describe("reconcile", () => {
  it("follows the cursor, and takes decisions on rows it holds from the states alone", async () => {
    const a = prop(1);
    await start(answer([a], [a]));
    live.mockResolvedValueOnce(answer([], [accepted(a)], { cursor: 1 }));
    await advance(LIVE_POLL_MS);
    expect(live).toHaveBeenLastCalledWith("uxr", 1);
    expect(shownIds()).toEqual(["1:tentative"]);
    expect(overlay().waitingAccept.has("q-p1-1|51")).toBe(true);
    await advance(3000);
    expect(shownIds()).toEqual(["1:accepted"]);
  });

  it("fetches in full when an id comes back for another quote or tag (SQLite reuses ids)", async () => {
    const a = prop(1);
    await start(answer([a], [a]));
    const reused = prop(1, { quote_id: 9999, dom_id: "q-p9-1" });
    live.mockResolvedValueOnce(answer([], [reused], { cursor: 1 }));
    await advance(LIVE_POLL_MS);
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
    await start(answer([b], [a, b], { cursor: 2 }));
    live.mockResolvedValueOnce(answer([a, b], [a, b], { cursor: 2 }));
    await advance(LIVE_POLL_MS);
    expect(live).toHaveBeenLastCalledWith("uxr", null);
  });

  it("drops a held row with no state", async () => {
    const a = prop(1);
    const b = prop(2);
    await start(answer([a, b], [a, b]));
    live.mockResolvedValueOnce(answer([], [b], { cursor: 2 }));
    await advance(LIVE_POLL_MS);
    expect(shownIds()).toEqual(["2:tentative"]);
  });

  it("stops reading after the first settled read", async () => {
    await start(answer([], [], SETTLED));
    await advance(LIVE_POLL_MS * 5);
    expect(live).toHaveBeenCalledTimes(1);
  });
});

describe("never shown before it is played", () => {
  it("holds a new row back from the cards, the counts and the flashes until it lands", async () => {
    await start(answer([], []));
    const rows = [prop(1), accepted(prop(2))];
    live.mockResolvedValueOnce(answer(rows, rows));
    await advance(LIVE_POLL_MS);

    expect(overlay().held.has(1)).toBe(true);
    expect(overlay().byQuote["q-p1-1"]).toBeUndefined();
    const storeProposal = { id: 1, tag_name: "tag51", group_name: "G", colour_set: "ux", colour_index: 0, confidence: 0.6, rationale: "" };
    expect(mergedProposals("q-p1-1", [storeProposal], [], overlay())).toEqual([]);
    // The cut's (or a catch-up's) tag, from a refetch: held back until it lands.
    expect(mergedTags("q-p1-2", [tagOf(52)], overlay())).toEqual([]);
    const cb = codebookWith(51, 52);
    const counted = applyLiveCounts(cb, getPlaybackSnapshot())!;
    expect(counted.groups[0].tags.map((t) => [t.tentative_count, t.count])).toEqual([[0, 0], [0, 0]]);
    expect(getPlaybackSnapshot().flashingTagIds.size).toBe(0);

    await advance(4000);
    expect(shownIds()).toEqual(["1:tentative", "2:accepted"]);
    const after = applyLiveCounts(cb, getPlaybackSnapshot())!;
    expect(after.groups[0].tags.map((t) => [t.tentative_count, t.count])).toEqual([[1, 0], [0, 1]]);
  });

  it("flashes an accepted landing on the card, the sidebar and the lens, then stops", async () => {
    await start(answer([], []));
    const row = accepted(prop(2));
    live.mockResolvedValueOnce(answer([row], [row], SETTLED));
    await advance(LIVE_POLL_MS);
    let seen = false;
    for (let i = 0; i < 80 && !seen; i++) {
      await advance(50);
      seen = getPlaybackSnapshot().flashingTagIds.has(52);
    }
    expect(seen).toBe(true);
    expect(getPlaybackSnapshot().flashingTagNames.has("tag52")).toBe(true);
    expect(getPlaybackSnapshot().flashingCardKeys.has("q-p1-2:tag52")).toBe(true);
    await advance(FLASH_MS + 100);
    expect(getPlaybackSnapshot().flashingTagIds.size).toBe(0);
    expect(getPlaybackSnapshot().flashingCardKeys.size).toBe(0);
  });
});

describe("pacing on the clock", () => {
  it("lands a big batch no faster than three times a second while the run goes on", async () => {
    await start(answer([], []));
    const rows = Array.from({ length: 60 }, (_, i) => prop(i + 1));
    live.mockResolvedValue(answer(rows, rows));
    const times = await landingTimes(20_000);
    expect(times.length).toBeGreaterThan(10);
    expect(maxInAnySecond(times)).toBeLessThanOrEqual(3);
  });

  it("plays the end's top-up as a final wave of about three seconds, strongest first, three a second at most", async () => {
    const rows = Array.from({ length: 30 }, (_, i) => prop(i + 1, { confidence: 0.5 + (i % 7) / 20 }));
    await start(answer(rows, rows));
    const topped = rows.map(accepted);
    live.mockResolvedValueOnce(answer([], topped, { ...SETTLED, cursor: 30 }));
    await advance(LIVE_POLL_MS + 60);
    // Strongest first (the first landing has gone already).
    const order = _queueForTest().map((id) => rows[id - 1].confidence);
    expect(order.length).toBeGreaterThan(20);
    expect(order).toEqual([...order].sort((a, b) => b - a));
    const times = await landingTimes(5000);
    expect(shownIds().every((s) => s.endsWith(":accepted"))).toBe(true);
    // Nine landings in all (the first counted above), the last within the three seconds.
    expect(times.length).toBe(8);
    expect(times[times.length - 1]).toBeLessThanOrEqual(3000);
    expect(times[times.length - 1] - times[0]).toBeGreaterThanOrEqual(2400);
    expect(maxInAnySecond(times)).toBeLessThanOrEqual(3);
  });

  it("keeps tentative arrivals in their order while the run goes on", async () => {
    await start(answer([], []));
    const rows = [0.4, 0.9, 0.6].map((c, i) => prop(i + 1, { confidence: c }));
    live.mockResolvedValueOnce(answer(rows, rows));
    await advance(LIVE_POLL_MS);
    expect(_queueForTest()).toEqual([1, 2, 3]);
  });

  it("lands at once, unflashed, under reduced motion", async () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
    try {
      await start(answer([], []));
      const rows = Array.from({ length: 20 }, (_, i) => accepted(prop(i + 1)));
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
  it("pauses, then catches up quickly, strongest first, when shown", async () => {
    await start(answer([], []));
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    const rows = Array.from({ length: 12 }, (_, i) => prop(i + 1, { confidence: (i + 1) / 20 }));
    live.mockResolvedValue(answer(rows, rows));
    await advance(10_000);
    expect(shownIds()).toHaveLength(0);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    document.dispatchEvent(new Event("visibilitychange"));
    await advance(50);
    // The strongest landed first.
    expect(Object.values(overlay().byQuote).flat().map((t) => t.id)).toContain(12);
    expect(Object.values(overlay().byQuote).flat().map((t) => t.id)).not.toContain(1);
    const times = await landingTimes(3500);
    expect(shownIds()).toHaveLength(12);
    expect(times[times.length - 1]).toBeLessThanOrEqual(3100);
    expect(maxInAnySecond(times)).toBeLessThanOrEqual(3);
  });
});

describe("an exported report", () => {
  it("follows nothing: no read, no overlay, the embedded data as it is", async () => {
    vi.mocked(isExportMode).mockReturnValue(true);
    followAutoCode("uxr", "first", JOB);
    await advance(LIVE_POLL_MS * 3);
    expect(live).not.toHaveBeenCalled();
    expect(overlay().held.size).toBe(0);
    const cb = codebookWith(51);
    expect(applyLiveCounts(cb, getPlaybackSnapshot())).toBe(cb);
    expect(document.documentElement.hasAttribute("data-autocode-tentative")).toBe(false);
  });
});

describe("the chip waits for the last tag (D11), within one bound", () => {
  const done = {
    status: "completed" as const, progressLabel: null, durationLabel: "1:00",
    errorMessage: null, partialMessage: null, hasProposals: true,
  };
  const status = { processed_quotes: 40, total_quotes: 40 } as never;

  it("holds while the run lands, ends once it has, and never past the bound", async () => {
    await start(answer([prop(1)], [prop(1)]));
    live.mockResolvedValue(answer([], [prop(1)], { cursor: 1 }));
    expect(playbackPending("uxr", JOB)).toBe(true);
    await advance(CHIP_WAIT_MS);
    expect(playbackPending("uxr", JOB)).toBe(false);
  });

  it("ends as soon as the settled run's queue is played out", async () => {
    await start(answer([], []));
    const rows = [accepted(prop(1))];
    live.mockResolvedValueOnce(answer(rows, rows, SETTLED));
    await advance(LIVE_POLL_MS);
    expect(playbackPending("uxr", JOB)).toBe(true);
    await advance(4000);
    expect(playbackPending("uxr", JOB)).toBe(false);
  });

  it("never waits in a hidden window, nor before a first read, nor after the reads failed, nor for another chip", async () => {
    live.mockReturnValueOnce(new Promise(() => {}));
    followAutoCode("uxr", "first", JOB);
    expect(playbackPending("uxr", JOB)).toBe(false);
    resetPlayback();
    live.mockReset();
    await start(answer([prop(1)], [prop(1)]));
    expect(playbackPending("uxr", JOB)).toBe(true);
    expect(playbackPending("uxr", "autocode:uxr:other")).toBe(false);
    Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
    expect(playbackPending("uxr", JOB)).toBe(false);
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    live.mockRejectedValue(new Error("down"));
    await advance(LIVE_POLL_MS * 6);
    expect(playbackPending("uxr", JOB)).toBe(false);
  });

  it("holds a finished chip at running, offering no Stop, and lets every other status by", async () => {
    await start(answer([prop(1)], [prop(1)]));
    live.mockResolvedValue(answer([], [prop(1)], { cursor: 1 }));
    expect(serverFinished("uxr", JOB)).toBe(false);
    expect(holdForPlayback("uxr", JOB, done, status)).toMatchObject({ status: "running", progressLabel: "40/40", landing: true });
    expect(serverFinished("uxr", JOB)).toBe(true);
    const failed = { ...done, status: "failed" as const };
    expect(holdForPlayback("uxr", JOB, failed, status)).toBe(failed);
    expect(holdForPlayback("norman", JOB, done, status)).toBe(done);
    await advance(CHIP_WAIT_MS);
    expect(holdForPlayback("uxr", JOB, done, status)).toBe(done);
  });

  it("does not wait again after the chip held: the run's reload fires within one bound", async () => {
    await start(answer([prop(1)], [prop(1)]));
    live.mockResolvedValue(answer([], [prop(1)], { cursor: 1 }));
    holdForPlayback("uxr", JOB, done, status);
    await advance(CHIP_WAIT_MS);
    let resolved = false;
    void whenPlayedOut("uxr", JOB).then(() => { resolved = true; });
    await advance(0);
    expect(resolved).toBe(true);
  });

  it("whenPlayedOut, for a chip that ended at once, resolves within the bound", async () => {
    await start(answer([prop(1)], [prop(1)]));
    live.mockResolvedValue(answer([], [prop(1)], { cursor: 1 }));
    let resolved = false;
    void whenPlayedOut("uxr", JOB).then(() => { resolved = true; });
    await advance(CHIP_WAIT_MS - 1000);
    expect(resolved).toBe(false);
    await advance(1500);
    expect(resolved).toBe(true);
  });
});

describe("a researcher's own decision", () => {
  it("accepting a tag waiting in the queue lands at once, never behind the playback", async () => {
    await start(answer([], []));
    const rows = Array.from({ length: 30 }, (_, i) => prop(i + 1));
    live.mockResolvedValue(answer(rows, rows, { cursor: 30 }));
    await advance(LIVE_POLL_MS);
    expect(_queuedForTest()).toBeGreaterThan(20);
    acceptLanding("q-p1-30", { ...landedTagFrom(rows[29]), shown: "tentative" });
    expect(shownIds()).toContain("30:accepted");
    expect(acceptProposal).toHaveBeenCalledWith(30, undefined);
    // The server still says pending on the next read: the decision holds.
    await advance(LIVE_POLL_MS);
    expect(shownIds()).toContain("30:accepted");
  });

  it("puts a failed accept back and says so", async () => {
    vi.mocked(acceptProposal).mockRejectedValueOnce({ status: 500 });
    await start(answer([prop(1)], [prop(1)]));
    acceptLanding("q-p1-1", landedTag(1));
    await advance(0);
    expect(shownIds()).toEqual(["1:tentative"]);
    expect(toastSaveFailed).toHaveBeenCalled();
  });

  it("a refusal caused by the playback lagging is retried as an override, and the researcher wins (D2)", async () => {
    // The server accepted row 1 live; the page has not read it yet.
    vi.mocked(denyProposal).mockRejectedValueOnce({ status: 409, reason: "proposal_accepted" });
    await start(answer([prop(1)], [prop(1)]));
    denyLanding("q-p1-1", landedTag(1));
    await advance(0);
    expect(denyProposal).toHaveBeenNthCalledWith(1, 1, undefined);
    expect(denyProposal).toHaveBeenNthCalledWith(2, 1, "accepted");
    expect(shownIds()).toEqual([]);
    expect(toastSaveFailed).not.toHaveBeenCalled();
  });

  it("✓ on a row the lines already accepted is sent as an override, so it becomes the researcher's", async () => {
    await start(answer([prop(1)], [prop(1)]));
    // Accepted on the server and read, but still waiting in the queue: the card shows it tentative.
    live.mockResolvedValueOnce(answer([], [accepted(prop(1)), prop(2)], { cursor: 1 }));
    live.mockResolvedValue(answer([prop(2)], [accepted(prop(1)), prop(2)], { cursor: 2 }));
    await advance(LIVE_POLL_MS);
    expect(shownIds()).toEqual(["1:tentative"]);
    acceptLanding("q-p1-1", landedTag(1));
    expect(acceptProposal).toHaveBeenCalledWith(1, "accepted");
  });

  it("a deny takes the tag off at once; removing a landed accepted tag overrides its acceptance", async () => {
    const rows = [prop(1), accepted(prop(2))];
    await start(answer(rows, rows));
    denyLanding("q-p1-1", landedTag(1));
    removeLanding("q-p1-2", landedTag(2), false, vi.fn());
    expect(shownIds()).toEqual([]);
    expect(denyProposal).toHaveBeenCalledWith(1, undefined);
    expect(denyProposal).toHaveBeenCalledWith(2, "accepted");
  });
});

function landedTagFrom(p: ProposedTagResponse): LiveTag {
  return {
    id: p.id, dom_id: p.dom_id, tag_definition_id: p.tag_definition_id, tag_name: p.tag_name,
    group_name: p.group_name, colour_set: p.colour_set, colour_index: p.colour_index,
    confidence: p.confidence, rationale: p.rationale, shown: "tentative",
  };
}

describe("decisions during the handover grace stick (review, HIGH)", () => {
  /** A settled run handed over, the quotes store reloaded with its cut. */
  async function handedOver() {
    const rows = [prop(1), prop(2), accepted(prop(3))];
    await start(answer(rows, rows, SETTLED));
    beginHandover("uxr", JOB);
    initFromQuotes([
      quote("q-p1-1", [], [{ id: 1, def: 51 }]),
      quote("q-p1-2", [], [{ id: 2, def: 52 }]),
      quote("q-p1-3", [tagOf(50)]),
    ], true);
  }
  const card = (domId: string) => {
    const s = getQuotesSnapshot();
    const tags = mergedTags(domId, s.tags[domId] ?? [], s.live);
    return {
      tags: tags.map((t) => t.id),
      proposed: mergedProposals(domId, s.proposedTags[domId] ?? [], tags, s.live).map((p) => p.id),
    };
  };

  it("accept, deny and remove go the ordinary way and survive the overlay going", async () => {
    await handedOver();
    acceptLanding("q-p1-1", landedTag(1));
    denyLanding("q-p1-2", landedTag(2));
    const s = getQuotesSnapshot();
    const three = landedTag(3);
    expect(storeCarries("q-p1-3", s.tags["q-p1-3"], three, s.live)).toBe(true);
    removeLanding("q-p1-3", three, true, () => removeTag("q-p1-3", "tag50", true, 50));
    await advance(0);
    // One request each, the ordinary one.
    expect(acceptProposal).toHaveBeenCalledTimes(1);
    expect(acceptProposal).toHaveBeenCalledWith(1);
    expect(denyProposal).toHaveBeenCalledTimes(1);
    expect(denyProposal).toHaveBeenCalledWith(2);
    expect(patchTags).toHaveBeenCalledTimes(1);
    const during = [card("q-p1-1"), card("q-p1-2"), card("q-p1-3")];
    expect(during).toEqual([
      { tags: [51], proposed: [] }, { tags: [], proposed: [] }, { tags: [], proposed: [] },
    ]);
    await advance(HANDOVER_GRACE_MS + 100);
    expect(overlay().held.size).toBe(0);
    expect([card("q-p1-1"), card("q-p1-2"), card("q-p1-3")]).toEqual(during);
  });

  it("a remove during a catch-up, after a quote reload, does not come back", async () => {
    const row = accepted(prop(3));
    await start(answer([row], [row]), "catchup");
    initFromQuotes([quote("q-p1-3", [tagOf(50)])], true);
    const s = getQuotesSnapshot();
    removeLanding("q-p1-3", landedTag(3), storeCarries("q-p1-3", s.tags["q-p1-3"], landedTag(3), s.live), () => removeTag("q-p1-3", "tag50", true, 50));
    await advance(0);
    expect(denyProposal).not.toHaveBeenCalled();
    expect(card("q-p1-3").tags).toEqual([]);
    // The server still says accepted on the next read: the exclusion holds.
    live.mockResolvedValue(answer([], [row], { cursor: 3 }));
    await advance(LIVE_POLL_MS * 2);
    expect(card("q-p1-3").tags).toEqual([]);
  });
});

describe("what a codebook read gains: never a double count (review, MEDIUM)", () => {
  it("adds a first apply's live acceptances whenever the read was made", async () => {
    const cb = await stampedRead(() => Promise.resolve(codebookWith(51)));
    await advance(10);
    await start(answer([accepted(prop(1))], [accepted(prop(1))]));
    const late = await stampedRead(() => Promise.resolve(codebookWith(51)));
    expect(applyLiveCounts(cb, getPlaybackSnapshot())!.groups[0].tags[0].count).toBe(1);
    expect(applyLiveCounts(late, getPlaybackSnapshot())!.groups[0].tags[0].count).toBe(1);
  });

  it("adds a catch-up's acceptances only when first seen after the read (they are tags already)", async () => {
    await start(answer([accepted(prop(1))], [accepted(prop(1))]), "catchup");
    await advance(10);
    const cb = await stampedRead(() => Promise.resolve(codebookWith(51)));
    await advance(10);
    const rows = [accepted(prop(1)), accepted(prop(4))];
    live.mockResolvedValueOnce(answer([prop(4, { status: "accepted", decided_by: "threshold" })], rows, { cursor: 4 }));
    await advance(LIVE_POLL_MS + 4000);
    // Row 1 was saved before the read (counted by it), row 4 after.
    expect(applyLiveCounts(cb, getPlaybackSnapshot())!.groups[0].tags[0].count).toBe(1);
    const later = await stampedRead(() => Promise.resolve(codebookWith(51)));
    expect(applyLiveCounts(later, getPlaybackSnapshot())!.groups[0].tags[0].count).toBe(0);
  });

  it("a researcher's accept counts only for a read made before it", async () => {
    await start(answer([prop(1)], [prop(1)]));
    const before = await stampedRead(() => Promise.resolve(codebookWith(51)));
    await advance(10);
    acceptLanding("q-p1-1", landedTag(1));
    await advance(10);
    const after = await stampedRead(() => Promise.resolve(codebookWith(51)));
    expect(applyLiveCounts(before, getPlaybackSnapshot())!.groups[0].tags[0].count).toBe(1);
    expect(applyLiveCounts(after, getPlaybackSnapshot())!.groups[0].tags[0].count).toBe(0);
  });

  it("a quote already tagged by hand is never added", async () => {
    initFromQuotes([quote("q-p1-1", [tagOf(51, "human")])], true);
    const cb = await stampedRead(() => Promise.resolve(codebookWith(51)));
    await start(answer([accepted(prop(1))], [accepted(prop(1))]));
    expect(applyLiveCounts(cb, getPlaybackSnapshot())!.groups[0].tags[0].count).toBe(0);
  });

  it("two codebooks landing at once each count their own (D21)", async () => {
    const two = {
      groups: [
        { ...codebookWith(51).groups[0], id: 1, framework_id: "uxr" },
        { ...codebookWith(77).groups[0], id: 2, framework_id: "norman" },
      ],
      ungrouped: [], all_tag_names: [],
    } as unknown as CodebookResponse;
    await start(answer([prop(1), accepted(prop(4))], [prop(1), accepted(prop(4))]));
    const n = [prop(10, { tag_definition_id: 77, tag_name: "tag77", dom_id: "q-x" })];
    await start(answer(n, n), "first", "norman", "autocode:norman:1");
    const counted = applyLiveCounts(two, getPlaybackSnapshot())!;
    expect(counted.groups[0].tags[0]).toMatchObject({ tentative_count: 1, count: 1 });
    expect(counted.groups[1].tags[0]).toMatchObject({ tentative_count: 1, count: 0 });
  });
});

describe("a follow belongs to its chip (review, MEDIUM)", () => {
  it("Stop then Resume before the stop settles: nothing blinks, the old chip's handover is ignored", async () => {
    const rows = [prop(1), accepted(prop(2))];
    await start(answer(rows, rows));
    const before = overlay();
    overlayWrites.mockClear();
    // Resume: a new chip for the codebook takes the follow over.
    live.mockResolvedValueOnce(answer([...rows, prop(3)], [...rows, prop(3)], { cursor: 3 }));
    followAutoCode("uxr", "first", "autocode:uxr:2");
    expect(overlay()).toBe(before);
    // The stopped run's chip completes and hands over: not this follow's.
    beginHandover("uxr", JOB);
    expect(getPlaybackSnapshot().frameworks.get("uxr")?.handoverAt).toBeNull();
    await advance(0);
    // The new read plays only what is new; nothing already landed flashes again.
    expect(_queueForTest()).toEqual([3]);
    await advance(3000);
    expect(shownIds()).toEqual(["1:tentative", "2:accepted", "3:tentative"]);
    expect(getPlaybackSnapshot().flashingTagIds.has(52)).toBe(false);
  });
});

describe("how often the quotes store changes (review, MEDIUM)", () => {
  it("idle polls change nothing; N landings change it at most N times; a flash ending never", async () => {
    const rows = Array.from({ length: 6 }, (_, i) => accepted(prop(i + 1)));
    await start(answer([], []));
    overlayWrites.mockClear();
    const snap = getPlaybackSnapshot();
    live.mockResolvedValue(answer([], [], { cursor: null }));
    await advance(LIVE_POLL_MS * 10);
    expect(live.mock.calls.length).toBeGreaterThan(8);
    expect(overlayWrites).not.toHaveBeenCalled();
    // Nor the snapshot the sidebar and the lens read.
    expect(getPlaybackSnapshot()).toBe(snap);

    live.mockResolvedValueOnce(answer(rows, rows, { cursor: 6 }));
    live.mockResolvedValue(answer([], rows, { cursor: 6 }));
    let landings = 0;
    let last = overlay();
    for (let t = 0; t < 30_000; t += 50) {
      await advance(50);
      if (overlay() !== last) landings++;
      last = overlay();
    }
    expect(shownIds()).toHaveLength(6);
    // The read that held them back changed the overlay once, then one write a landing.
    expect(overlayWrites.mock.calls.length).toBeLessThanOrEqual(landings);
    expect(overlayWrites.mock.calls.length).toBeLessThanOrEqual(6 + 1);
    // Every flash has ended by now, with no write of its own.
    expect(getPlaybackSnapshot().flashingCardKeys.size).toBe(0);
  });
});

describe("the run's end", () => {
  it("fires no bn:tags-changed or codebook-changed of its own, batch after batch", async () => {
    await start(answer([], []));
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
    await start(answer([prop(1)], [prop(1)], SETTLED));
    const before = await stampedRead(() => Promise.resolve(codebookWith(51)));
    await advance(1);
    beginHandover("uxr", JOB);
    const after = await stampedRead(() => Promise.resolve(codebookWith(51)));
    const fw = getPlaybackSnapshot().frameworks.get("uxr")!;
    expect(snapshotHasRun(before, fw)).toBe(false);
    expect(snapshotHasRun(after, fw)).toBe(true);
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
    await start(answer([prop(1)], [prop(1)]));
    expect(root.getAttribute("data-autocode-tentative")).toBe("pulse");
    live.mockResolvedValueOnce(answer([], [prop(1)], { ...SETTLED, cursor: 1 }));
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
      await start(answer([], []));
      live.mockResolvedValueOnce(answer([prop(1)], [prop(1)]));
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
