/**
 * Organisms / AutoCode review — the review dialog's Levels control: the
 * confidence histogram inside the dual threshold slider, and the zone
 * counters, as ThresholdReviewModal composes them, in its
 * `.codebook-modal-body.threshold-body`. The zone rows and their tags are on
 * the tag specimen.
 */

import { useState } from "react";

import { ConfidenceHistogram } from "../../../components/ConfidenceHistogram";
import { DualThresholdSlider } from "../../../components/DualThresholdSlider";
import { ZoneCounters } from "../../../components/ZoneCounters";
import { outcomeZone, snapLines } from "../../../utils/recut";
import type { ProposedTagResponse } from "../../../utils/types";
import type { SpecimenMeta, SpecimenStory } from "../csf";

export default {
  title: "Organisms/AutoCode review",
  description:
    "DualThresholdSlider around ConfidenceHistogram, and ZoneCounters (molecules/threshold-review.css), at the review dialog's default lines (0.30 and 0.70).",
  caveat: "Live: drag either line; the zones and counters follow, counted by the dialog's own rule (outcomeZone at the snapped lines).",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Levels"] as const;

/** 40 proposals spread the way a real run spreads them: a hump of confident ones, a tail of guesses. */
const CONFIDENCES = [
  0.08, 0.12, 0.15, 0.18, 0.22, 0.24, 0.27, 0.31, 0.33, 0.36, 0.38, 0.41, 0.44, 0.46, 0.48, 0.52, 0.55, 0.57, 0.6,
  0.62, 0.64, 0.66, 0.68, 0.71, 0.72, 0.74, 0.75, 0.77, 0.78, 0.8, 0.81, 0.82, 0.84, 0.85, 0.86, 0.88, 0.9, 0.92, 0.94, 0.97,
];

const PROPOSALS: ProposedTagResponse[] = CONFIDENCES.map((confidence, i) => ({
  id: 900 + i,
  quote_id: 500 + i,
  dom_id: `q-sg-review-${i}`,
  session_id: `s${(i % 6) + 1}`,
  speaker_code: `p${(i % 6) + 1}`,
  start_timecode: 60 * i,
  quote_text: "Fixture quote.",
  tag_definition_id: 70 + (i % 5),
  tag_name: ["hidden cost", "comparison shopping", "delivery anxiety", "convention", "memory lapse"][i % 5],
  group_name: ["Trust", "Trust", "Emotion", "Usability", "Usability"][i % 5],
  colour_set: ["trust", "trust", "emo", "ux", "ux"][i % 5],
  colour_index: i % 5,
  confidence,
  rationale: "Fixture rationale.",
  status: "pending",
}));

/** Counts each zone by the modal's own rule: `outcomeZone` at the snapped lines, no stored cut. */
function zoneCounts(lower: number, upper: number) {
  const lines = snapLines(lower, upper);
  const counts = { accepted: 0, tentative: 0, excluded: 0 };
  for (const p of PROPOSALS) counts[outcomeZone(p, null, lines)] += 1;
  return counts;
}

function LevelsControl() {
  const [lower, setLower] = useState(0.3);
  const [upper, setUpper] = useState(0.7);
  const { excluded, tentative, accepted } = zoneCounts(lower, upper);
  return (
    <div className="codebook-modal-body threshold-body">
      <DualThresholdSlider lower={lower} upper={upper} onLowerChange={setLower} onUpperChange={setUpper}>
        <ConfidenceHistogram proposals={PROPOSALS} lower={lower} upper={upper} />
      </DualThresholdSlider>
      <ZoneCounters excluded={excluded} tentative={tentative} accepted={accepted} />
    </div>
  );
}

export const Levels: SpecimenStory = {
  name: "Histogram, lines and counters (live)",
  render: () => <LevelsControl />,
};
