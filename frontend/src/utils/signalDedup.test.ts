import { describe, it, expect } from "vitest";
import { dedupeSignals, isSentimentSignal, isFromSentimentLens } from "./signalDedup";
import type { UnifiedSignal, UnifiedQuote } from "./types";

function q(pid: string, at: number): UnifiedQuote {
  return {
    text: "…", pid, sessionId: "s1", startSeconds: at, intensity: 2,
    tagNames: [], colourSet: "", tagColourIndices: {},
  };
}

function sig(
  columnLabel: string,
  compositeSignal: number,
  quotes: UnifiedQuote[],
  extra: Partial<UnifiedSignal> = {},
): UnifiedSignal {
  return {
    key: `section|Beds|${columnLabel}`,
    location: "Beds",
    sourceType: "section",
    columnLabel,
    colourSet: "ux",
    codebookName: "UX Research",
    participants: [...new Set(quotes.map((x) => x.pid))],
    nEff: 1, meanIntensity: 2, concentration: 1.5,
    compositeSignal, quotes,
    ...extra,
  };
}

const labels = (out: UnifiedSignal[]) => out.map((s) => s.columnLabel);

describe("dedupeSignals", () => {
  it("keeps a card that brings a quote no stronger card carries", () => {
    const a = sig("Structure", 0.6, [q("p1", 10), q("p2", 20)]);
    const b = sig("Behaviour", 0.5, [q("p2", 20), q("p3", 30)]);
    expect(labels(dedupeSignals([a, b]))).toEqual(["Structure", "Behaviour"]);
  });

  it("hides a card whose quotes are all already on the page", () => {
    const strong = sig("Structure", 0.6, [q("p1", 10), q("p2", 20), q("p3", 30)]);
    const subset = sig("Feedback", 0.2, [q("p1", 10), q("p2", 20)]);
    expect(labels(dedupeSignals([strong, subset]))).toEqual(["Structure"]);
  });

  it("hides a card whose quotes are split across two stronger cards", () => {
    // The case a subset-of-ONE test would miss: nothing new on screen either way.
    const a = sig("Scope", 1.0, [q("p1", 10)]);
    const b = sig("Feedback", 0.6, [q("p2", 20)]);
    const split = sig("Discoverability", 0.3, [q("p1", 10), q("p2", 20)]);
    expect(labels(dedupeSignals([a, b, split]))).toEqual(["Scope", "Feedback"]);
  });

  it("breaks a tie on quote count, so the bigger card wins", () => {
    // Equal composites, and the labels are chosen so ALPHABETICAL order
    // disagrees with count — otherwise the final localeCompare tie-break gives
    // the right answer for the wrong reason and this test cannot fail. (It
    // could not, until a mutation run caught it: dropping the count tie-break
    // left all eight green.)
    const big = sig("Zebra", 0.214, [q("p1", 40), q("p1", 50), q("p2", 70)]);
    const smallSubset = sig("Alpha", 0.214, [q("p1", 40), q("p2", 70)]);
    // Alpha sorts first alphabetically but covers less. Count wins, so Zebra is
    // ranked first and Alpha — a strict subset of it — is hidden.
    expect(labels(dedupeSignals([big, smallSubset]))).toEqual(["Zebra"]);
  });

  it("never hides the Sentiment card", () => {
    const a = sig("Scope", 1.0, [q("p1", 10), q("p3", 30)]);
    const b = sig("Feedback", 0.6, [q("p1", 10), q("p2", 20), q("p3", 30)]);
    const sent = sig("Sentiment", 0.55, [q("p1", 10), q("p2", 20), q("p3", 30)], {
      codebookName: "Sentiment", colourSet: "",
    });
    // Its three quotes are all covered by Scope + Feedback. It stays anyway.
    expect(labels(dedupeSignals([a, b, sent]))).toContain("Sentiment");
  });

  it("de-duplicates each location independently", () => {
    const beds = sig("Structure", 0.6, [q("p1", 10), q("p2", 20)]);
    const bedsDup = sig("Feedback", 0.2, [q("p1", 10)]);
    const bag = { ...sig("Feedback", 0.5, [q("p1", 10)]), location: "Bag" };
    // Bag's card cites the same triple, but it is a different location and
    // must not be suppressed by Beds' coverage.
    expect(labels(dedupeSignals([beds, bedsDup, bag]))).toEqual(["Structure", "Feedback"]);
    expect(dedupeSignals([beds, bedsDup, bag]).map((s) => s.location))
      .toEqual(["Beds", "Bag"]);
  });

  it("returns cards in the caller's order, not its own ranking", () => {
    const weak = sig("Feedback", 0.1, [q("p9", 90)]);
    const strong = sig("Structure", 0.9, [q("p1", 10)]);
    expect(labels(dedupeSignals([weak, strong]))).toEqual(["Feedback", "Structure"]);
  });

  it("keeps a card with no quotes rather than silently dropping it", () => {
    const empty = sig("Mystery", 0.4, []);
    expect(labels(dedupeSignals([empty]))).toEqual(["Mystery"]);
  });
});

describe("isFromSentimentLens", () => {
  const base = sig("Sentiment", 0.5, [q("p1", 1)]);

  it("is false for the Sentiment GROUP card, which is a codebook card", () => {
    // The sentiment framework's display name is "Emotional & Cognitive
    // Signals". Styling this as a sentiment VALUE looks up `badge-Sentiment`,
    // a class that does not exist, and takes the wrong participant denominator.
    expect(isFromSentimentLens({ ...base, codebookName: "Emotional & Cognitive Signals" }))
      .toBe(false);
  });

  it("is true for a card from the sentiment lens, which names no codebook", () => {
    expect(isFromSentimentLens({ ...base, columnLabel: "frustration", codebookName: "" }))
      .toBe(true);
  });

  it("exempts both kinds from de-duplication all the same", () => {
    expect(isSentimentSignal({ ...base, codebookName: "Emotional & Cognitive Signals" })).toBe(true);
    expect(isSentimentSignal({ ...base, columnLabel: "frustration", codebookName: "" })).toBe(true);
    expect(isSentimentSignal({ ...base, columnLabel: "Structure", codebookName: "Garrett" })).toBe(false);
  });
});
