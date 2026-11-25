/**
 * Organisms / Signal card — the Signals lens's card (`SignalCard` in
 * islands/SignalsPage.tsx), in `.signal-compound-page .signal-cards`, the
 * containers SignalsPage draws it in. Its metrics are the `Metric` cells, which
 * only lay out inside the card's grid; this is where they belong.
 */

import { useState } from "react";

import { SignalCard } from "../../SignalsPage";
import type { UnifiedQuote, UnifiedSignal } from "../../../utils/types";
import type { SpecimenMeta, SpecimenStory } from "../csf";
import { Measured } from "../measure";

export default {
  title: "Organisms/Signal card",
  description:
    "SignalCard (organisms/signals.css) with its hero, Metric rows, evidence quotes and footer: a sentiment signal and a codebook signal with a finding.",
  caveat:
    "Click a card to select it. Its hero opens the chart (the Metric rows); that is your own reading preference, shared with the Signals lens, so the page leaves it as you have it. Speaker names come from the open project, so the quotes show codes here.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Cards"] as const;

const PIDS = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"];

function q(pid: string, text: string, start: number, intensity: number, tagNames: string[] = [], colourSet = ""): UnifiedQuote {
  return { text, pid, sessionId: `s${pid.slice(1)}`, startSeconds: start, intensity, tagNames, colourSet, tagColourIndices: {}, quoteId: `q-sg-sig-${pid}-${start}` };
}

const SENTIMENT: UnifiedSignal = {
  key: "sg-sentiment",
  location: "Checkout",
  sourceType: "section",
  anchor: "section-checkout",
  columnLabel: "frustration",
  colourSet: "",
  codebookName: "Sentiment",
  participants: ["p1", "p3", "p4", "p6", "p7"],
  nEff: 4.6,
  meanIntensity: 2.4,
  concentration: 3.1,
  compositeSignal: 0.82,
  label: "Frustration",
  labelKind: "value",
  quotes: [
    q("p1", "Twelve pounds for delivery? No.", 912, 3),
    q("p3", "I didn't know if it would come before the weekend, so I just closed the tab.", 1404, 2),
    q("p4", "The button just sat there greyed out.", 2210, 2),
    q("p6", "Why does it want my phone number?", 655, 2),
    q("p7", "I'd expect it to say how much delivery is before I pay.", 1781, 2),
  ],
};

const CODEBOOK: UnifiedSignal = {
  key: "sg-codebook",
  location: "Checkout",
  sourceType: "section",
  anchor: "section-checkout",
  columnLabel: "Trust",
  colourSet: "trust",
  codebookName: "Trust and credibility",
  participants: ["p2", "p3", "p5", "p8"],
  nEff: 3.8,
  meanIntensity: 1.9,
  concentration: 2.2,
  compositeSignal: 0.61,
  signalName: "Delivery cost arrives too late to trust the total",
  elaboration:
    "Four participants hesitated when delivery appeared at the last step; two left. None objected to the cost itself, only to learning it late.",
  label: "Trust",
  labelKind: "group",
  flag: "Problem",
  quotes: [
    q("p2", "Oh, now it's more. Why didn't it say that before?", 1502, 2, ["hidden cost"], "trust"),
    q("p3", "I'd want to see the full price on the product page.", 1611, 2, ["hidden cost"], "trust"),
    q("p5", "That's the kind of thing that makes me check somewhere else.", 1890, 2, ["comparison shopping"], "trust"),
    q("p8", "Fine, but I'm screenshotting this in case it changes again.", 2050, 1, ["hidden cost"], "trust"),
  ],
};

function SignalCards() {
  const [selected, setSelected] = useState<string | null>("sg-codebook");
  return (
    <section className="signal-compound-page" aria-label="Checkout">
      <div className="signal-cards">
        {[SENTIMENT, CODEBOOK].map((s, i) => (
          <SignalCard
            key={s.key}
            signal={s}
            allPids={PIDS}
            isSentiment={s === SENTIMENT}
            isFocused={selected === s.key}
            onSelect={() => setSelected(s.key)}
            elaborationsIn
            siblingSignals={[SENTIMENT.compositeSignal, CODEBOOK.compositeSignal]}
            signalIndex={i}
          />
        ))}
      </div>
    </section>
  );
}

export const Cards: SpecimenStory = {
  name: "A sentiment signal, and a selected codebook signal with a finding",
  render: () => (
    <Measured selectors={[".signal-card", ".signal-card-metrics"]}>
      <SignalCards />
    </Measured>
  ),
};
