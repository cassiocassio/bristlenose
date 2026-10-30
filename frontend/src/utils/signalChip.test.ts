import { describe, expect, it } from "vitest";
import { signalAccent } from "./signalChip";
import type { UnifiedSignal } from "./types";

const signal = (over: Partial<UnifiedSignal>): UnifiedSignal => ({
  key: "k", location: "Checkout", sourceType: "section", anchor: "section-1",
  columnLabel: "Sentiment", colourSet: "", codebookName: "", participants: [], nEff: 1,
  meanIntensity: 1, concentration: 1, compositeSignal: 1, quotes: [], ...over,
});

describe("signalAccent: the hue a card, its keyline, its ink and its navigation tag share", () => {
  it("is the sentiment colour of the fallback lens's value cards", () => {
    expect(signalAccent(signal({ columnLabel: "frustration" }), true)).toBe("var(--bn-sentiment-frustration)");
  });

  it("is the named feeling's own colour for a codebook card that names one feeling", () => {
    // Every card of the Sentiment codebook shares one colour set, so without this they are all one teal.
    expect(
      signalAccent(signal({ colourSet: "sentiment", label: "frustration", labelKind: "value" }), false),
    ).toBe("var(--bn-sentiment-frustration)");
    expect(
      signalAccent(signal({ colourSet: "sentiment", label: "Delight", labelKind: "value" }), false),
    ).toBe("var(--bn-sentiment-delight)");
  });

  it("keeps the colour set's bar for a direction, a mixed card and a codebook group", () => {
    expect(signalAccent(signal({ colourSet: "sentiment", label: "Negative", labelKind: "valence" }), false))
      .toBe("var(--bn-bar-sentiment)");
    expect(signalAccent(signal({ colourSet: "emo", label: "Needs and desires", labelKind: "group" }), false))
      .toBe("var(--bn-bar-emo)");
  });

  it("falls back to the accent when there is nothing else", () => {
    expect(signalAccent(signal({}), false)).toBe("var(--bn-colour-accent)");
  });
});
