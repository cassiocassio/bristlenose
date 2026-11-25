/**
 * Atoms / Small charts — the inline data marks that draw on their own:
 * intensity dots and the sparkline. Two siblings wait for their organisms,
 * because their CSS only exists there: MicroBar is styled under `.tag-sidebar`
 * (and the codebook), and Metric is a run of cells in a signal card's grid.
 */

import { IntensityDots } from "../../../components/IntensityDots";
import { Sparkline, type SparklineItem } from "../../../components/Sparkline";
import { SENTIMENT_ORDER } from "../../../utils/sentimentOrder";
import type { SpecimenMeta, SpecimenStory } from "../csf";

export default {
  title: "Atoms/Small charts",
  description:
    "IntensityDots and Sparkline (molecules/sparkline.css), with the props their callers pass.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Dots", "Sparklines"] as const;

export const Dots: SpecimenStory = {
  name: "Intensity dots, 0 to 3 in halves, both sizes",
  render: () => (
    <div className="bn-sg-specimens">
      {[0, 0.5, 1, 1.5, 2, 2.5, 3].map((v) => (
        <span key={v} className="bn-sg-labelled">
          <IntensityDots value={v} />
          <IntensityDots value={v} size="s" />
          <code className="bn-sg-token">{v}</code>
        </span>
      ))}
    </div>
  ),
};

/** Fed as SessionsTable feeds it: one bar per sentiment, coloured by its token. */
function sentimentItems(counts: Record<string, number>): SparklineItem[] {
  return SENTIMENT_ORDER.map((s) => ({ key: s, count: counts[s] ?? 0, colour: `var(--bn-sentiment-${s})` }));
}

export const Sparklines: SpecimenStory = {
  name: "Sentiment sparkline, a session's spread and an empty one",
  render: () => (
    <div className="bn-sg-specimens">
      <Sparkline items={sentimentItems({ frustration: 6, confusion: 3, doubt: 2, surprise: 1, satisfaction: 4, delight: 2, confidence: 1 })} />
      <Sparkline items={sentimentItems({ frustration: 1, satisfaction: 9, delight: 5 })} />
      <Sparkline items={sentimentItems({})} emptyContent={<span className="bn-sg-measure">no sentiment</span>} />
    </div>
  ),
};
