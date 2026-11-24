/**
 * Which lanes a session's timeline has, from the whole session's data: never from the zoom or the
 * scroll. One rule, read by the timeline that draws the lanes (components/SessionTapestry.tsx) and
 * by the transcript's detail menu that offers them (contexts/TranscriptTimelineStore.ts,
 * islands/transcript/TimelineSplit.tsx), so the menu cannot offer a lane the timeline would not
 * draw. Outside the timeline's lazy chunk, so the store and the menu can import it.
 */

import type { TapestryLanes } from "../components/SessionTapestry";
import type { TapestrySession } from "./types";

type Turn = TapestrySession["turns"][number];

/** A moderator or observer slot (m1, o1): the team, drawn on the Moderator lane. */
export const isTeamCode = (code: string) => /^[mo]/.test(code);

/** The server's per-turn answer wins (it reads the slot's role); otherwise the displayed code. */
export function isTeamTurn(tn: Turn, codeOf: (slot: string) => string = (slot) => slot): boolean {
  return typeof tn.team === "boolean" ? tn.team : isTeamCode(codeOf(tn.speaker));
}

/** The most detail a session can draw, from its quotes: Sentiment needs a quote, Themes a quote in
 *  a theme. Every session with a timeline has the speaker lanes. */
export function mostLanes(quotes: readonly { theme: string | null }[]): TapestryLanes {
  if (quotes.some((q) => q.theme)) return 5;
  return quotes.length > 0 ? 3 : 2;
}

export interface SessionLanes {
  /** The Sections lane: the session has at least one section flag. */
  sections: boolean;
  /** The Moderator lane: at least one turn is the team's. */
  team: boolean;
  /** The most detail it can draw (mostLanes). Participant and the time axis always draw. */
  most: TapestryLanes;
}

export function sessionLanes(
  s: Pick<TapestrySession, "sections" | "turns" | "quotes">,
  codeOf?: (slot: string) => string,
): SessionLanes {
  return {
    sections: s.sections.length > 0,
    team: s.turns.some((tn) => isTeamTurn(tn, codeOf)),
    most: mostLanes(s.quotes),
  };
}
