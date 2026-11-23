/**
 * The tag sidebar's AutoCode overview (docs/design-autocode-landing-plan.md Phase 6; mockup
 * docs/mockups/tag-sidebar-autocode-histogram.html): the summary line in each state, merged and
 * split, Review inactive during a run, the state remembered per study, opening by itself once,
 * and the scale that only grows while a run lands.
 */

import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { TagOverviewResponse, ZoneBin } from "../utils/types";

vi.mock("../utils/api", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    getTagOverview: vi.fn(),
    patchTagOverview: vi.fn(() => Promise.resolve()),
    getCodebook: vi.fn(),
    getHiddenTagGroups: vi.fn(),
    patchHiddenTagGroups: vi.fn(() => Promise.resolve()),
    getFrameworkStates: vi.fn(),
    apiGet: vi.fn(),
  };
});

vi.mock("../utils/exportData", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, isExportMode: vi.fn(() => false) };
});

const landed: { id: number; tag_definition_id: number; confidence: number; shown: "tentative" | "accepted" }[] = [];
vi.mock("../contexts/AutoCodePlaybackView", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, loadedEngine: () => ({ liveProposals: () => landed }) };
});

import { TagOverview } from "./TagOverview";
import { TagSidebar } from "./TagSidebar";
import {
  apiGet,
  getCodebook,
  getFrameworkStates,
  getHiddenTagGroups,
  getTagOverview,
  patchTagOverview,
} from "../utils/api";
import { isExportMode } from "../utils/exportData";
import { resetPlaybackView, setPlaybackSnapshot, EMPTY_SNAPSHOT } from "../contexts/AutoCodePlaybackView";
import { resetStore } from "../contexts/QuotesContext";
import { requestSoloTag, resetSidebarStore, toggleTagGroupHidden } from "../contexts/SidebarStore";
import { liveZoneBins, nextScales, plainCounts, splitAround, markupRuns } from "../utils/tagOverview";
import type { CodebookResponse } from "../utils/types";

// ── Data ──────────────────────────────────────────────────────────────────

function bins(spec: Record<number, Partial<ZoneBin>>): (ZoneBin & { lower: number })[] {
  return Array.from({ length: 20 }, (_, i) => ({
    lower: i / 20, accepted: 0, tentative: 0, excluded: 0, ...(spec[i] ?? {}),
  }));
}

const UXR_BINS = bins({ 2: { excluded: 3 }, 10: { tentative: 5 }, 16: { accepted: 4 } });

function served(
  codebooks: TagOverviewResponse["codebooks"],
  state: Partial<Pick<TagOverviewResponse, "open" | "split" | "auto_opened">> = {},
): TagOverviewResponse {
  return { open: false, split: false, auto_opened: true, ...state, codebooks };
}

const uxr = (over: Partial<TagOverviewResponse["codebooks"][number]> = {}) => ({
  framework_id: "uxr", coding: false, lower: 0.3, upper: 0.7, bins: UXR_BINS, ...over,
});
const norman = (over: Partial<TagOverviewResponse["codebooks"][number]> = {}) => ({
  framework_id: "norman", coding: false, lower: 0.25, upper: 0.6,
  bins: bins({ 12: { tentative: 2 }, 18: { accepted: 1 } }), ...over,
});

const BOOKS = [
  { id: "uxr", title: "Bristlenose UXR Codebook", tagCount: 34 },
  { id: "norman", title: "The Design of Everyday Things", tagCount: 28 },
];

function renderOverview(props: Partial<Parameters<typeof TagOverview>[0]> = {}) {
  const onReview = vi.fn();
  const utils = render(
    <div>
      <TagOverview
        candidates={BOOKS}
        plain={{ tags: 70, codebooks: 3 }}
        filterText={null}
        quoteCount={400}
        onReview={onReview}
        {...props}
      />
    </div>,
  );
  return { ...utils, onReview };
}

const line = () => screen.getByTestId("bn-tag-summary");

beforeEach(() => {
  vi.clearAllMocks();
  landed.length = 0;
  resetPlaybackView();
  vi.mocked(isExportMode).mockReturnValue(false);
  vi.mocked(getTagOverview).mockResolvedValue(served([]));
});

// ── The line ──────────────────────────────────────────────────────────────

describe("the summary line", () => {
  it("before any run counts every tag but Sentiment's, as words with no control (D22)", async () => {
    renderOverview({ plain: { tags: 70, codebooks: 3 } });
    await waitFor(() => expect(getTagOverview).toHaveBeenCalled());
    expect(line().textContent).toBe("70 tags from 3 codebooks");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("before any run, with one codebook, is the count alone, singular when it is one", async () => {
    renderOverview({ plain: { tags: 1, codebooks: 1 } });
    await waitFor(() => expect(getTagOverview).toHaveBeenCalled());
    expect(line().textContent).toBe("1 tag");
  });

  it("with one reviewable codebook reads its tag count, then Review (D17)", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()]));
    renderOverview();
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview-review")).toBeTruthy());
    expect(screen.getByTestId("bn-tag-overview-toggle").textContent).toBe("34 tags");
    expect(screen.queryByTestId("bn-tag-overview-split")).toBeNull();
  });

  it("with several reads their tags from a codebook count that is its own control", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr(), norman()]));
    renderOverview();
    const link = await waitFor(() => screen.getByTestId("bn-tag-overview-split"));
    expect(link.textContent).toBe("2 codebooks");
    expect(screen.getByTestId("bn-tag-overview-toggle").textContent).toBe("62 tags from");
    // No Review on the line with two or more: each codebook's is in the split view.
    expect(screen.queryByTestId("bn-tag-overview-review")).toBeNull();
  });

  it("under search or Used keeps today's live match count", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr(), norman()]));
    renderOverview({ filterText: "2 tags across 1 frameworks" });
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview-toggle")).toBeTruthy());
    expect(screen.getByTestId("bn-tag-overview-toggle").textContent).toBe("2 tags across 1 frameworks");
    expect(screen.queryByTestId("bn-tag-overview-split")).toBeNull();
  });

  it("is absent from an export: no read, and D22's words", async () => {
    vi.mocked(isExportMode).mockReturnValue(true);
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()]));
    renderOverview({ plain: { tags: 34, codebooks: 1 } });
    await act(async () => { await Promise.resolve(); });
    expect(getTagOverview).not.toHaveBeenCalled();
    expect(line().textContent).toBe("34 tags");
    expect(screen.queryByTestId("bn-tag-overview")).toBeNull();
    // Whatever else the page holds: a codebook the playback speaks for draws nothing either.
    const fw = { kind: "first" as const, handoverAt: null, tentative: new Map(), accepted: [] };
    act(() => setPlaybackSnapshot({ ...EMPTY_SNAPSHOT, frameworks: new Map([["uxr", fw]]) }));
    expect(line().textContent).toBe("34 tags");
    expect(screen.queryByTestId("bn-tag-overview-toggle")).toBeNull();
  });
});

// ── Merged and split ──────────────────────────────────────────────────────

describe("merged and split", () => {
  it("draws one merged chart with no ticks and no Review, then one per codebook with both", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr(), norman()], { open: true }));
    renderOverview();
    const body = await waitFor(() => screen.getByTestId("bn-tag-overview"));
    expect(body.querySelectorAll("[data-testid=bn-overview-histogram]")).toHaveLength(1);
    expect(body.querySelector(".threshold-histogram-tick")).toBeNull();
    expect(screen.queryByTestId("bn-tag-overview-review")).toBeNull();
    // The tally: chart order, the numbers on their own.
    expect(body.querySelector(".tag-overview-tally")?.textContent).toBe("Excluded 3 · Tentative 7 · Accepted 5");

    fireEvent.click(screen.getByTestId("bn-tag-overview-split"));
    const split = screen.getAllByTestId("bn-tag-overview-book");
    expect(split).toHaveLength(2);
    expect(split[0].textContent).toContain("Bristlenose UXR Codebook");
    expect(split[0].querySelectorAll(".threshold-histogram-tick")).toHaveLength(2);
    expect(screen.getAllByTestId("bn-tag-overview-review")).toHaveLength(2);
    expect(patchTagOverview).toHaveBeenLastCalledWith({ open: true, split: true });

    fireEvent.click(screen.getByTestId("bn-tag-overview-split"));
    expect(screen.queryAllByTestId("bn-tag-overview-book")).toHaveLength(0);
    expect(patchTagOverview).toHaveBeenLastCalledWith({ open: true, split: false });
  });

  it("the codebook count, clicked while closed, opens the overview split", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr(), norman()]));
    renderOverview();
    fireEvent.click(await waitFor(() => screen.getByTestId("bn-tag-overview-split")));
    expect(screen.getAllByTestId("bn-tag-overview-book")).toHaveLength(2);
    expect(patchTagOverview).toHaveBeenLastCalledWith({ open: true, split: true });
  });

  it("colours the tally's numbers by zone", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()], { open: true }));
    renderOverview();
    const body = await waitFor(() => screen.getByTestId("bn-tag-overview"));
    expect(body.querySelector(".tag-overview-n--acc")?.textContent).toBe("4");
    expect(body.querySelector(".tag-overview-n--ten")?.textContent).toBe("5");
    expect(body.querySelector(".tag-overview-n--exc")?.textContent).toBe("3");
  });
});

// ── Review ────────────────────────────────────────────────────────────────

describe("Review", () => {
  it("opens the dialog for its codebook when the run has finished", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()]));
    const { onReview } = renderOverview();
    fireEvent.click(await waitFor(() => screen.getByTestId("bn-tag-overview-review")));
    expect(onReview).toHaveBeenCalledWith(expect.objectContaining({ id: "uxr", title: "Bristlenose UXR Codebook" }));
  });

  it("is present but inactive while the first apply codes (D17)", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr({ coding: true })]));
    const { onReview } = renderOverview();
    const review = await waitFor(() => screen.getByTestId("bn-tag-overview-review"));
    expect(review.getAttribute("aria-disabled")).toBe("true");
    fireEvent.click(review);
    expect(onReview).not.toHaveBeenCalled();
  });

  it("is inactive while the page lands a first apply the read predates, live again for a catch-up", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()]));
    renderOverview();
    const review = await waitFor(() => screen.getByTestId("bn-tag-overview-review"));
    const fw = { kind: "first" as const, handoverAt: null, tentative: new Map(), accepted: [] };
    act(() => setPlaybackSnapshot({ ...EMPTY_SNAPSHOT, frameworks: new Map([["uxr", fw]]) }));
    expect(review.getAttribute("aria-disabled")).toBe("true");
    act(() => setPlaybackSnapshot({ ...EMPTY_SNAPSHOT, frameworks: new Map([["uxr", { ...fw, kind: "catchup" as const }]]) }));
    expect(review.getAttribute("aria-disabled")).toBeNull();
  });
});

// ── Remembered, and opening once ──────────────────────────────────────────

describe("remembered per study (D12)", () => {
  it("draws what the study remembers and saves what the researcher changes", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr(), norman()], { open: true, split: true }));
    renderOverview();
    await waitFor(() => expect(screen.getAllByTestId("bn-tag-overview-book")).toHaveLength(2));
    fireEvent.click(screen.getByTestId("bn-tag-overview-toggle"));
    expect(screen.queryByTestId("bn-tag-overview")).toBeNull();
    expect(patchTagOverview).toHaveBeenCalledWith({ open: false, split: true });
    fireEvent.click(screen.getByTestId("bn-tag-overview-toggle"));
    expect(screen.getAllByTestId("bn-tag-overview-book")).toHaveLength(2);
    expect(patchTagOverview).toHaveBeenLastCalledWith({ open: true, split: true });
  });

  it("opens by itself once, after a first run, and says so to the server", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()], { auto_opened: false }));
    renderOverview();
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview")).toBeTruthy());
    expect(patchTagOverview).toHaveBeenCalledTimes(1);
    expect(patchTagOverview).toHaveBeenCalledWith({ open: true, auto_opened: true });
  });

  it("stays closed on a study it has opened itself on before", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()], { auto_opened: true, open: false }));
    renderOverview();
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview-toggle")).toBeTruthy());
    expect(screen.queryByTestId("bn-tag-overview")).toBeNull();
    expect(patchTagOverview).not.toHaveBeenCalled();
  });

  it("waits for the run to end: it does not open while the first apply codes", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr({ coding: true })], { auto_opened: false }));
    renderOverview();
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview-toggle")).toBeTruthy());
    expect(screen.queryByTestId("bn-tag-overview")).toBeNull();
    // The run ends: the page re-reads at its handover.
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()], { auto_opened: false }));
    act(() => { document.dispatchEvent(new CustomEvent("bn:tags-changed")); });
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview")).toBeTruthy());
    expect(patchTagOverview).toHaveBeenCalledWith({ open: true, auto_opened: true });
  });
});

// ── Live, and the scale that only grows (D19) ─────────────────────────────

describe("live", () => {
  it("grows the chart from the playback while a run lands", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr({ coding: true, lower: null, upper: null, bins: bins({}) })], { open: true }));
    renderOverview();
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview")).toBeTruthy());
    landed.push(
      { id: 1, tag_definition_id: 1, confidence: 0.85, shown: "accepted" },
      { id: 2, tag_definition_id: 1, confidence: 0.5, shown: "tentative" },
      { id: 3, tag_definition_id: 1, confidence: 0.1, shown: "tentative" },
    );
    const fw = { kind: "first" as const, handoverAt: null, tentative: new Map(), accepted: [] };
    act(() => setPlaybackSnapshot({ ...EMPTY_SNAPSHOT, frameworks: new Map([["uxr", fw]]) }));
    // Below the lower line a landing tentative tag is drawn where the cut will put it.
    expect(screen.getByTestId("bn-tag-overview").querySelector(".tag-overview-tally")?.textContent)
      .toBe("Excluded 1 · Tentative 1 · Accepted 1");
  });

  it("only grows, in rounded steps, while a run lands; rescales once when it ends", () => {
    const col = (n: number): ZoneBin[] => Array.from({ length: 20 }, (_, i) => ({ accepted: i === 0 ? n : 0, tentative: 0, excluded: 0 }));
    let s = nextScales(null, [{ id: "m", bins: col(3), live: true }], "m");
    expect(s.m).toBe(5);
    s = nextScales(s, [{ id: "m", bins: col(6), live: true }], "m");
    expect(s.m).toBe(10); // 6 × 1.25 = 7.5, up to the next round step
    s = nextScales(s, [{ id: "m", bins: col(4), live: true }], "m");
    expect(s.m).toBe(10); // never shrinks while landing
    s = nextScales(s, [{ id: "m", bins: col(7), live: false }], "m");
    expect(s.m).toBe(7); // the run has ended: one rescale, to the tallest
  });

  it("in split view, a finished chart holds its scale while another lands", () => {
    const col = (n: number): ZoneBin[] => Array.from({ length: 20 }, (_, i) => ({ accepted: i === 0 ? n : 0, tentative: 0, excluded: 0 }));
    let s = nextScales(null, [
      { id: "m", bins: col(20), live: false },
      { id: "a", bins: col(12), live: false },
      { id: "b", bins: col(8), live: false },
    ], "m");
    expect([s.a, s.b]).toEqual([12, 12]); // one shared scale at rest
    s = nextScales(s, [
      { id: "m", bins: col(40), live: true },
      { id: "a", bins: col(12), live: false },
      { id: "b", bins: col(28), live: true },
    ], "m");
    expect(s.a).toBe(12); // held
    expect(s.b).toBe(50); // grew: 28 × 1.25 = 35, up to 50
    s = nextScales(s, [
      { id: "m", bins: col(40), live: false },
      { id: "a", bins: col(12), live: false },
      { id: "b", bins: col(28), live: false },
    ], "m");
    expect([s.a, s.b, s.m]).toEqual([28, 28, 40]);
  });
});

// ── Pure helpers ──────────────────────────────────────────────────────────

describe("helpers", () => {
  it("never counts Sentiment before a run, and counts only codebooks with tags", () => {
    const fw = (id: string, n: number) => ({ id, groups: [{ tags: Array.from({ length: n }) }] });
    expect(plainCounts([fw("sentiment", 7), fw("_user", 4), fw("uxr", 34), fw("norman", 0)]))
      .toEqual({ tags: 38, codebooks: 2 });
  });

  it("splits a sentence round its link, wherever the language puts it", () => {
    expect(splitAround("96 tags from <link>3 codebooks</link>", "link"))
      .toEqual({ before: "96 tags from ", inner: "3 codebooks", after: "" });
    expect(splitAround("<link>3 コードブック</link>の96 個のタグ", "link"))
      .toEqual({ before: "", inner: "3 コードブック", after: "の96 個のタグ" });
    expect(markupRuns("A <exc>1</exc> · B <acc>2</acc>", ["exc", "acc"]).map((r) => r.tag))
      .toEqual([null, "exc", null, "acc"]);
  });

  it("keeps what the server had excluded under a landing run", () => {
    const server = bins({ 1: { excluded: 2, tentative: 9 } });
    const out = liveZoneBins(server, [{ confidence: 0.9, shown: "accepted" }], 0.3);
    expect(out[1]).toEqual({ accepted: 0, tentative: 0, excluded: 2 });
    expect(out[18].accepted).toBe(1);
  });
});

// ── Through the sidebar ───────────────────────────────────────────────────

function codebook(): CodebookResponse {
  const g = (id: number, name: string, fw: string | null, tags: string[]) => ({
    id, name, subtitle: "", colour_set: "", order: id, is_default: fw === null,
    total_quotes: 0, framework_id: fw,
    tags: tags.map((n, i) => ({ id: id * 100 + i, name: n, count: 0, colour_index: i })),
  });
  return {
    groups: [
      g(1, "Sentiment", "sentiment", ["frustration", "delight"]),
      g(2, "Uncategorised", null, ["storage", "gift"]),
      g(3, "Trust", "uxr", ["credibility", "risk", "proof"]),
      g(4, "Affordances", "norman", ["signifier", "mapping"]),
    ],
    ungrouped: [],
    all_tag_names: [],
  };
}

describe("in the tag sidebar", () => {
  // The dialog is a lazy chunk: load it first, so a cold import cannot race the test.
  beforeAll(async () => {
    await import("./ThresholdReviewModal");
  });

  beforeEach(() => {
    resetStore();
    resetSidebarStore();
    vi.mocked(getCodebook).mockResolvedValue(codebook());
    vi.mocked(getHiddenTagGroups).mockResolvedValue([]);
    vi.mocked(getFrameworkStates).mockResolvedValue({});
    vi.mocked(apiGet).mockResolvedValue({ project_name: "ikea" });
  });

  it("counts the reviewable codebook only: never Sentiment, never the researcher's own tags", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()]));
    render(<TagSidebar />);
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview-review")).toBeTruthy());
    expect(screen.getByTestId("bn-tag-overview-toggle").textContent).toBe("3 tags");
  });

  it("before any run counts every tag but Sentiment's, own tags included (D22)", async () => {
    render(<TagSidebar />);
    await waitFor(() => expect(screen.getByText("credibility")).toBeTruthy());
    expect(line().textContent).toBe("7 tags from 3 codebooks");
  });

  it("drops a codebook whose eye is closed", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr(), norman()]));
    render(<TagSidebar />);
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview-split")).toBeTruthy());
    act(() => toggleTagGroupHidden("Affordances"));
    expect(screen.queryByTestId("bn-tag-overview-split")).toBeNull();
    expect(screen.getByTestId("bn-tag-overview-toggle").textContent).toBe("3 tags");
  });

  it("is dimmed with the other controls in solo mode, not hidden", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()], { open: true }));
    requestSoloTag("credibility");
    const { container } = render(<TagSidebar />);
    await waitFor(() => expect(container.querySelector(".tag-solo-active")).toBeTruthy());
    await waitFor(() => expect(screen.getByTestId("bn-tag-overview")).toBeTruthy());
    expect(container.querySelector(".tag-solo-active .tag-sidebar-subtitle.tag-overview-line")).toBeTruthy();
  });

  it("opens the review dialog for the codebook", async () => {
    vi.mocked(getTagOverview).mockResolvedValue(served([uxr()]));
    render(<TagSidebar />);
    fireEvent.click(await waitFor(() => screen.getByTestId("bn-tag-overview-review")));
    await waitFor(() => expect(screen.getByTestId("bn-threshold-overlay")).toBeTruthy());
    expect(screen.getByText(/AutoCode Review/).textContent).toContain("Bristlenose UXR Codebook");
  });
});
