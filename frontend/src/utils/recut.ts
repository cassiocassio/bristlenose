/**
 * Where the AutoCode review's Apply leaves each proposal: the client's copy of the
 * re-cut rule in `bristlenose/server/routes/autocode.py` (`recut_target`), so the
 * dialog's counters and zone lists show the outcome over the whole run before Apply
 * is pressed (docs/design-autocode-landing-plan.md, Phase 2: D2, D26, D39).
 */
import type { ProposedTagResponse } from "./types";
import { snapToStep } from "./confidenceStep";

export type Zone = "accepted" | "tentative" | "excluded";

/** A pair of lines: accept at or above `upper`, exclude strictly below `lower`. */
export interface Lines {
  lower: number;
  upper: number;
}

/** A decision the review's lines never move: the researcher's, or one made before who
 *  decided was recorded ("unknown"), which is held the same way (D2). */
export function isPinned(p: ProposedTagResponse): boolean {
  return p.status !== "pending" && (p.decided_by === "researcher" || p.decided_by === "unknown");
}

/** The zone a confidence falls in under `lines`, by the server's inequalities. */
export function zoneAt(confidence: number, lines: Lines): Zone {
  if (confidence >= lines.upper) return "accepted";
  if (confidence < lines.lower) return "excluded";
  return "tentative";
}

/** Where a proposal sits now, by its status. */
export function statusZone(p: ProposedTagResponse): Zone {
  if (p.status === "accepted") return "accepted";
  if (p.status === "denied") return "excluded";
  return "tentative";
}

/**
 * Where Apply at `lines` would leave `p`. A pinned decision stays where it is. A
 * pending proposal is undecided, so Apply decides it by the new lines, as shipped
 * (N175, D41). A threshold decision moves only when its zone under the `stored` lines
 * differs from its zone under the new ones (D26), so Apply with the lines unmoved
 * leaves every decision as it is. `stored` is null for a run no lines were ever
 * stored on: Apply is then a plain cut, and every decision stays.
 */
export function outcomeZone(p: ProposedTagResponse, stored: Lines | null, lines: Lines): Zone {
  const now = statusZone(p);
  if (isPinned(p)) return now;
  if (p.status === "pending") return zoneAt(p.confidence, lines);
  if (stored === null) return now;
  const was = zoneAt(p.confidence, stored);
  const after = zoneAt(p.confidence, lines);
  return was === after ? now : after;
}

/** The lines a job was last cut at, snapped to the 0.05 grid as the server reads them
 *  (`stored_lines`): a missing one is the default; null when neither was ever stored. */
export function storedLinesOf(
  job: { applied_lower_threshold: number | null; applied_upper_threshold: number | null },
  defaults: Lines,
): Lines | null {
  const lo = job.applied_lower_threshold;
  const hi = job.applied_upper_threshold;
  if (lo == null && hi == null) return null;
  return { lower: snapToStep(lo ?? defaults.lower), upper: snapToStep(hi ?? defaults.upper) };
}

/** The slider positions as Apply sends them: on the 0.05 grid. */
export function snapLines(lower: number, upper: number): Lines {
  return { lower: snapToStep(lower), upper: snapToStep(upper) };
}
