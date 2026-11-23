/**
 * Where the AutoCode review's Apply leaves each proposal: the client's copy of the
 * re-cut rule in `bristlenose/server/routes/autocode.py` (`recut_target`), so the
 * dialog's counters and zone lists show the outcome over the whole run before Apply
 * is pressed (docs/design-autocode-landing-plan.md, Phase 2: D2, D26, D39).
 */
import type { ProposedTagResponse } from "./types";

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
 * Where Apply at `lines` would leave `p`. A pinned decision stays where it is. Any
 * other proposal moves only when its zone under the `stored` lines differs from its
 * zone under the new ones (D26), so Apply with the lines unmoved changes nothing.
 * `stored` is null for a run no lines were ever stored on: Apply is then a plain cut,
 * as it always was, sorting only the pending proposals by the new lines.
 */
export function outcomeZone(p: ProposedTagResponse, stored: Lines | null, lines: Lines): Zone {
  const now = statusZone(p);
  if (isPinned(p)) return now;
  if (stored === null && p.status !== "pending") return now;
  const after = zoneAt(p.confidence, lines);
  const was = stored ? zoneAt(p.confidence, stored) : now;
  return was === after ? now : after;
}
