/**
 * Discussion lens — data contract, version 1.
 *
 * The shape the lens renders. The server sends the stage's record
 * (`bristlenose/discussion/models.py`) with speaker codes only;
 * `loadDiscussion` joins names from `/sessions` to build this. One record per project: the guide as written
 * (`spine`), the merged record of what was planned and what was asked
 * (`sections`), every moderator turn, and every quote with the question it
 * answers and the section it was routed to.
 */

export interface DiscussionParticipant {
  code: string;
  name: string;
}

export interface DiscussionSession {
  id: string;          // "s1"
  number: number;      // 1
  participants: DiscussionParticipant[];
  duration: string;    // "07:39"
  seconds: number;
  /** Why a session contributes nothing — never read as "no questions asked". */
  state?: "ok" | "failed" | "no_moderator" | "moderator_unreliable";
}

/** Where an item was asked: one per moderator turn. */
export interface DiscussionAsk {
  turn: string;        // "s1@01:16"
  session: string;
  sec: number;
}

export type ItemSource = "planned" | "asked" | "both";

export interface DiscussionItem {
  id: string;          // a planned item keeps its guide id ("s3.2"); an asked one is "a4"
  terse: string;
  verbatim: string;
  source: ItemSource;  // planned = in the guide, never asked; asked = not in the guide
  placed: "" | "flow"; // "flow" = a homeless question code placed by timing
  role: "opening" | "core" | "closing";
  asks: DiscussionAsk[];
}

export interface DiscussionSection {
  id: string;
  title: string;
  heading: string;
  kind: "questions" | "task" | "instruction";
  origin: "planned" | "emergent";
  items: DiscussionItem[];
}

export interface SpineSection {
  id: string;
  title: string;
  kind: "questions" | "task" | "instruction";
  items: { id: string; terse: string; text: string }[];
}

export interface DiscussionTurn {
  id: string;
  session: string;
  sec: number;
  time: string;
  text: string;
  /** "unclassified": an askable turn the model never labelled. Always shown —
   *  hiding it with the non-questions would lose a question silently (§9.A). */
  kind: "planned" | "adlib" | "new" | "instruction" | "chat" | "unclassified";
  item: string | null; // the merged item this turn asks, or null for a non-question
  speaker?: string;    // the moderator's code; "m1" when the record predates the field
}

export interface DiscussionQuote {
  key: string;
  session: string;
  participant: string;
  name: string;
  sec: number;
  time: string;
  text: string;
  after_item: string | null;
  section: string | null;
  how: "agree" | "topic" | "anchor" | "unrouted";
  sentiment?: string | null;
}

export interface DiscussionData {
  version: 1;
  guide: boolean;
  /** A guide that is there but went unread, and why ("" = read, or none). */
  guide_problem?: string;
  sessions: DiscussionSession[];
  spine: SpineSection[];
  sections: DiscussionSection[];
  standalone: DiscussionItem[];
  turns: DiscussionTurn[];
  quotes: DiscussionQuote[];
}
