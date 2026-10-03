/**
 * Discussion lens — pure derivations from the data contract. No DOM, no React,
 * so every rule the lens shows is testable on its own (model.test.ts).
 */

import type {
  DiscussionData,
  DiscussionItem,
  DiscussionParticipant,
  DiscussionQuote,
  DiscussionTurn,
} from "./types";

/** The navigator's two views. Labels (3 Oct 2026): "merged" is shown as
 *  "Normalised questions", "planned" as "Your guide". */
export type Mode = "planned" | "merged";

/** Within Your guide: the guide's short labels, or its own wording. */
export type GuideView = "summary" | "original";

/** Provenance mark in the navigator's margin. */
export type Mark = "dot" | "hollow" | "plus";

export interface NavHead {
  type: "head";
  id: string;
  title: string;
  badge?: "instruction" | "new";
}

export interface NavRow {
  type: "row";
  id: string;          // the merged item id — the same id in Planned and Merged
  text: string;
  title: string;       // full wording, for the tooltip
  mark: Mark;
  sessions: string[];  // where it was asked, in session order
}

export type NavEntry = NavHead | NavRow;

/** Sessions an item was asked in, in the order the sessions are listed. */
export function itemSessions(item: DiscussionItem, order: string[]): string[] {
  const asked = new Set(item.asks.map((a) => a.session));
  return order.filter((s) => asked.has(s));
}

export function markOf(item: DiscussionItem): Mark {
  if (item.source === "both") return "dot";
  if (item.source === "planned") return "hollow";
  return "plus"; // ad-lib on topic, placed by flow, or in a new section: one mark
}

export function sessionOrder(data: DiscussionData): string[] {
  return data.sessions.map((s) => s.id);
}

/** Merged: the record — sections as run, every item with its provenance. */
export function mergedEntries(data: DiscussionData): NavEntry[] {
  const order = sessionOrder(data);
  const out: NavEntry[] = [];
  for (const s of data.sections) {
    out.push({
      type: "head",
      id: s.id,
      title: s.title,
      badge: s.kind === "instruction" ? "instruction" : s.origin === "emergent" ? "new" : undefined,
    });
    for (const it of s.items) {
      out.push({ type: "row", id: it.id, text: it.terse, title: it.verbatim,
        mark: markOf(it), sessions: itemSessions(it, order) });
    }
  }
  if (data.standalone.length) {
    out.push({ type: "head", id: "standalone", title: "Standalone" });
    for (const it of data.standalone) {
      out.push({ type: "row", id: it.id, text: it.terse, title: it.verbatim,
        mark: "plus", sessions: itemSessions(it, order) });
    }
  }
  return out;
}

/** Planned: the guide as written. Every line is planned, so every line carries the
 *  solid dot; where it was asked comes from the merged item with the same id. */
export function plannedEntries(data: DiscussionData, view: GuideView = "summary"): NavEntry[] {
  const order = sessionOrder(data);
  const merged = new Map<string, DiscussionItem>();
  for (const s of data.sections) for (const it of s.items) merged.set(it.id, it);
  const out: NavEntry[] = [];
  for (const s of data.spine) {
    out.push({ type: "head", id: s.id, title: s.title,
      badge: s.kind === "instruction" ? "instruction" : undefined });
    for (const it of s.items) {
      const m = merged.get(it.id);
      out.push({ type: "row", id: it.id, text: view === "original" ? it.text : it.terse,
        title: it.text, mark: "dot",
        sessions: m ? itemSessions(m, order) : [] });
    }
  }
  return out;
}

export function navEntries(data: DiscussionData, mode: Mode, view: GuideView = "summary"): NavEntry[] {
  return mode === "planned" && data.guide ? plannedEntries(data, view) : mergedEntries(data);
}

// ── the session column ──────────────────────────────────────────────────────

export interface AskWithAnswers {
  turn: DiscussionTurn;
  answers: DiscussionQuote[];
}

export interface QuestionGroup {
  asks: AskWithAnswers[];
  /** The group ended the session with no answers (nothing to fold forward into). */
  trailing: boolean;
}

export interface SessionColumn {
  before: DiscussionQuote[];   // quotes before the first question
  groups: QuestionGroup[];
}

/** Each quote answers the last question asked at or before it (1 s of slack for
 *  transcript rounding). Consecutive questions that drew no quotes fold forward
 *  into the next question that did, as one group. */
export function sessionColumn(data: DiscussionData, session: string): SessionColumn {
  const asked = data.turns
    .filter((t) => t.session === session && (t.item || t.kind === "unclassified"))
    .sort((a, b) => a.sec - b.sec);
  const quotes = data.quotes.filter((q) => q.session === session).sort((a, b) => a.sec - b.sec);
  const answers = new Map<string, DiscussionQuote[]>(asked.map((t) => [t.id, []]));
  const before: DiscussionQuote[] = [];
  for (const q of quotes) {
    let last: DiscussionTurn | undefined;
    for (const t of asked) {
      if (t.sec <= q.sec + 1) last = t;
      else break;
    }
    (last ? answers.get(last.id)! : before).push(q);
  }
  const groups: QuestionGroup[] = [];
  let cur: AskWithAnswers[] = [];
  for (const t of asked) {
    const a = answers.get(t.id)!;
    cur.push({ turn: t, answers: a });
    if (a.length) {
      groups.push({ asks: cur, trailing: false });
      cur = [];
    }
  }
  if (cur.length) groups.push({ asks: cur, trailing: true });
  return { before, groups };
}

export function sessionStats(data: DiscussionData, session: string): { questions: number; quotes: number } {
  return {
    questions: data.turns.filter((t) => t.session === session && t.item).length,
    quotes: data.quotes.filter((q) => q.session === session).length,
  };
}

// ── names ───────────────────────────────────────────────────────────────────

/** Header form, capped so a group session stays the size of a pair: up to two
 *  names in the locale's list form ("Sarah and Mike"), else "Bettina and 4 others". */
export function capNames(
  people: DiscussionParticipant[],
  list: (names: string[]) => string,
  others: (first: string, n: number) => string,
): string {
  const names = people.map((p) => p.name).filter(Boolean);
  if (names.length <= 2) return list(names);
  return others(names[0], names.length - 1);
}

// ── focus ───────────────────────────────────────────────────────────────────

/** Sticky, click-driven focus: an item (from a navigator row) or one asked turn
 *  (from a question in the session column). */
export interface Focus {
  item: string;
  turn: string | null;
}

/** Which questions in the session column a focus lights. */
export function litTurns(data: DiscussionData, session: string, focus: Focus | null): Set<string> {
  if (!focus) return new Set();
  if (focus.turn) return new Set([focus.turn]);
  return new Set(data.turns.filter((t) => t.session === session && t.item === focus.item).map((t) => t.id));
}

/** Clicking a row the current session never asked jumps to the first session that did. */
export function sessionForFocus(current: string, rowSessions: string[]): string {
  return rowSessions.length && !rowSessions.includes(current) ? rowSessions[0] : current;
}

/** A collapsed badge row shows the current session if it is among them, else the first. */
export function shownSession(current: string, rowSessions: string[]): string {
  return rowSessions.includes(current) ? current : rowSessions[0];
}

/** Wire geometry: a path from a navigator row (left edge of the gutter) to a
 *  question (right edge), or a stub with a chevron when one end is off screen. */
export interface WireEnd {
  y: number;
  /** -1 above the visible pane, 1 below, 0 on screen. */
  off: -1 | 0 | 1;
}

export function wirePath(from: WireEnd, to: WireEnd, width: number): { d: string; stub: boolean } | null {
  if (from.off && to.off) return null;
  if (from.off || to.off) {
    const leftEnd = !!to.off;              // the navigator end is on screen
    const x = leftEnd ? 0 : width;
    const dir = leftEnd ? 1 : -1;
    const y = leftEnd ? from.y : to.y;
    const up = (leftEnd ? to.off : from.off) < 0;
    const xe = x + dir * 22;
    const cy = up ? -4 : 4;
    return { d: `M${x},${y} h${dir * 22} M${xe - 3},${y - cy} L${xe},${y + cy} L${xe + 3},${y - cy}`, stub: true };
  }
  return { d: `M0,${from.y} h8 L${width - 8},${to.y} h8`, stub: false };
}
