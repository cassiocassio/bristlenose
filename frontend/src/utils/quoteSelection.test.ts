import { describe, expect, it } from "vitest";
import { selectQuotes } from "./quoteSelection";
import type { UnifiedQuote, UnifiedSignal } from "./types";

// Selection is editorial. The obvious design — show the quotes that prove the
// label — produces a card that only ever agrees with itself, which is a card
// you stop reading. These pin the thing that makes it worth having.

const q = (
  pid: string,
  t: number,
  intensity: number,
  tags: string[],
): UnifiedQuote => ({
  text: `${pid}@${t}`,
  pid,
  sessionId: "s1",
  startSeconds: t,
  intensity,
  tagNames: tags,
  colourSet: "sentiment",
  tagColourIndices: {},
});

const card = (quotes: UnifiedQuote[], over: Partial<UnifiedSignal> = {}): UnifiedSignal => ({
  key: "k",
  location: "Checkout",
  sourceType: "section",
  columnLabel: "Sentiment",
  colourSet: "sentiment",
  codebookName: "Sentiment",
  participants: [...new Set(quotes.map((x) => x.pid))],
  nEff: 2,
  meanIntensity: 2,
  concentration: 1.5,
  compositeSignal: 0.4,
  quotes,
  label: "frustration",
  labelKind: "value",
  ...over,
});

describe("below the cap, nothing is selected", () => {
  it("shows everything, in (participant, time) order", () => {
    const quotes = [q("p2", 10, 3, ["frustration"]), q("p1", 20, 1, ["delight"])];
    const { shown, dissenting } = selectQuotes(card(quotes), 4);
    expect(shown.map((x) => x.text)).toEqual(["p1@20", "p2@10"]);
    expect(dissenting).toBeNull();
  });
});

describe("above the cap", () => {
  const quotes = [
    q("p1", 10, 1, ["frustration"]),
    q("p1", 20, 3, ["frustration"]),
    q("p2", 30, 2, ["frustration"]),
    q("p2", 40, 3, ["frustration"]),
    q("p3", 50, 3, ["delight"]),
  ];

  it("keeps the strongest quotes that carry the finding", () => {
    const { shown } = selectQuotes(card(quotes), 4);
    // The intensity-1 frustration is the one dropped, not an arbitrary one.
    expect(shown.find((x) => x.text === "p1@10")).toBeUndefined();
    expect(shown).toHaveLength(4);
  });

  it("holds a slot for the voice that argues with the finding", () => {
    const { shown, dissenting } = selectQuotes(card(quotes), 4);
    expect(dissenting?.text).toBe("p3@50");
    expect(shown).toContain(dissenting);
  });

  it("RETURNS THEM IN (participant, time) ORDER — sequences depend on it", () => {
    // detectSequences fuses same-participant quotes that are ADJACENT in the
    // array. Returning them by strength would scatter runs and could
    // manufacture a false one, since the check never verifies chronology.
    const { shown } = selectQuotes(card(quotes), 4);
    const pairs = shown.map((x) => [x.pid, x.startSeconds] as const);
    const sorted = [...pairs].sort((a, b) => a[0].localeCompare(b[0]) || a[1] - b[1]);
    expect(pairs).toEqual(sorted);
  });

  it("does not spend the slot on a passing remark", () => {
    const weak = [...quotes.slice(0, 4), q("p3", 50, 1, ["delight"])];
    const { dissenting, shown } = selectQuotes(card(weak), 4);
    expect(dissenting).toBeNull();
    expect(shown.every((x) => x.tagNames.includes("frustration"))).toBe(true);
  });
});

describe("what 'supports the finding' means on each kind of card", () => {
  const mixed = [
    q("p1", 10, 3, ["frustration"]),
    q("p1", 20, 3, ["confusion"]),
    q("p2", 30, 3, ["doubt"]),
    q("p2", 40, 1, ["delight"]),
    q("p3", 50, 3, ["satisfaction"]),
  ];

  it("a direction card supports every value on its side", () => {
    const { shown, dissenting } = selectQuotes(
      card(mixed, { label: "Negative", labelKind: "valence" }), 4,
    );
    expect(dissenting?.tagNames).toEqual(["satisfaction"]);
    const negatives = shown.filter((x) =>
      ["frustration", "confusion", "doubt"].includes(x.tagNames[0]));
    expect(negatives).toHaveLength(3);
  });

  it("a card labelled mixed reserves nothing — it is divided by definition", () => {
    const { dissenting } = selectQuotes(
      card(mixed, { label: "Mixed sentiments", labelKind: "mixed" }), 4,
    );
    expect(dissenting).toBeNull();
  });

  it("falls back to forcefulness when nothing identifiably supports the label", () => {
    // A codebook card, whose tags are not sentiments. It must not invent a
    // preference, and it must not return fewer quotes than the cap.
    const codebook = [
      q("p1", 10, 1, ["system response"]),
      q("p1", 20, 3, ["system response"]),
      q("p2", 30, 2, ["delayed feedback"]),
      q("p2", 40, 3, ["delayed feedback"]),
      q("p3", 50, 2, ["confirmation"]),
    ];
    const { shown } = selectQuotes(
      card(codebook, { label: "Feedback", labelKind: "group", columnLabel: "Feedback" }), 4,
    );
    expect(shown).toHaveLength(4);
    expect(shown.find((x) => x.text === "p1@10")).toBeUndefined();
  });
});
