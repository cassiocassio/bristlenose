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
  badge?: "instruction";
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
      // The approved mockup badges an instruction section only. (A "new" badge on
      // emergent sections was added in the port without a decision; removed 3 Oct.)
      badge: s.kind === "instruction" ? "instruction" : undefined,
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

/** One session's asked questions in order, each with the quotes that answer it: a
 *  quote answers the last question asked at or before it (1 s of slack for
 *  transcript rounding). Quotes before the first question are `before`. */
function sessionAnswers(data: DiscussionData, session: string) {
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
  return { asked, answers, before };
}

/** Consecutive questions that drew no quotes fold forward into the next question
 *  that did, as one group. */
export function sessionColumn(data: DiscussionData, session: string): SessionColumn {
  const { asked, answers, before } = sessionAnswers(data, session);
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

// ── all sessions (decided 17–18 Oct 2026; plan §3 "All sessions") ───────────

/** The session bar's first choice: every session, read by question. Never a
 *  session id (those are "s1", "s2"…). */
export const ALL = "*all";

/** Item → session → that session's asks of the item, each with its answers. The
 *  same rule as the session column, so the All view and the navigator's measure
 *  count exactly what a session view shows under each question. */
export type ItemAnswers = Map<string, Map<string, AskWithAnswers[]>>;

export function itemAnswers(data: DiscussionData): ItemAnswers {
  const out: ItemAnswers = new Map();
  for (const s of data.sessions) {
    const { asked, answers } = sessionAnswers(data, s.id);
    for (const t of asked) {
      if (!t.item) continue; // an unclassified turn belongs to no question
      let bySession = out.get(t.item);
      if (!bySession) out.set(t.item, (bySession = new Map()));
      const list = bySession.get(s.id) ?? [];
      list.push({ turn: t, answers: answers.get(t.id) ?? [] });
      bySession.set(s.id, list);
    }
  }
  return out;
}

/** What All shows outside the guide's questions, per session: quotes before the
 *  first question, and asks the model never classified with their answers. With
 *  itemAnswers this accounts for every quote, so All loses none (review, 18 Oct). */
export interface Leftovers {
  before: DiscussionQuote[];
  unclassified: AskWithAnswers[];
}

export function sessionLeftovers(data: DiscussionData): Map<string, Leftovers> {
  const out = new Map<string, Leftovers>();
  for (const s of data.sessions) {
    const { asked, answers, before } = sessionAnswers(data, s.id);
    const unclassified = asked.filter((t) => !t.item).map((t) => ({ turn: t, answers: answers.get(t.id) ?? [] }));
    if (before.length || unclassified.length) out.set(s.id, { before, unclassified });
  }
  return out;
}

/** The quotes one session gave one question. */
export function cellQuotes(answers: ItemAnswers, item: string, session: string): number {
  return (answers.get(item)?.get(session) ?? []).reduce((n, a) => n + a.answers.length, 0);
}

/** The study's thirds: every asked cell that drew a quote, ranked by its count;
 *  a cell's shade is the third it falls in. Normalised to the study, so a dark
 *  cell means "among this study's richest answers" whatever the study's scale. */
export function yieldThirds(counts: number[]): [number, number, number] {
  const v = counts.filter((n) => n > 0).sort((a, b) => a - b);
  if (!v.length) return [0, 0, 0];
  return [v[Math.ceil(v.length / 3) - 1], v[Math.ceil((2 * v.length) / 3) - 1], v[v.length - 1]];
}

/** 0 = nothing to shade (not asked, or asked and no quotes: drawn alike, 18 Oct);
 *  1–3 = the lower, middle and upper third. When the cells differ, the study's richest
 *  is always the darkest, even where ties or a short study put it in a lower third.
 *  When every cell drew the same, there is nothing to rank: all take the middle step. */
export function shadeStep(quotes: number, thirds: [number, number, number]): 0 | 1 | 2 | 3 {
  if (quotes <= 0) return 0;
  const [low, mid, max] = thirds;
  if (max === low) return 2;
  if (quotes >= max) return 3;
  return quotes <= low ? 1 : quotes <= mid ? 2 : 3;
}

/** The row's bar, logarithmic: some data is much better than none, so the first
 *  quote is the biggest step (one of a maximum ten fills about a third). 0–1. */
export function barShare(quotes: number, max: number): number {
  if (quotes <= 0 || max <= 0) return 0;
  return Math.min(1, Math.log1p(quotes) / Math.log1p(max));
}

/** The navigator's measure, chosen by measuring: the grid (one cell per session
 *  under heads, then the bar) when it fits beside the shortest question text,
 *  else a strip of thin cells, else the bar and count, which fit anywhere. */
export type Tier = "bar" | "strip" | "grid";
export const MEASURE = {
  textMin: 130,   // the narrowest a question's text may get
  rowChrome: 38,  // a row's padding and its mark column (the guide's own padding is measured)
  gap: 12,        // between the text and the measure, and between the cells and the count
  bar: 72,        // bar + count (discussion.css: .dl-bar-box 48px, a gap, the count)
  count: 28,      // count alone
  strip: 8,       // a strip cell's pitch
  hysteresis: 20, // stepping UP a tier needs this much to spare, so a scrollbar appearing
                  // (up to 17px) when the grid's taller head arrives cannot flip it back
} as const;

const RANK: Record<Tier, number> = { bar: 0, strip: 1, grid: 2 };

/** `width` is the guide's content width (its padding already taken off). `current`, when
 *  given, is the tier showing now: stepping up from it needs MEASURE.hysteresis spare. */
export function measureTier(width: number, sessions: number, pitch: number, current?: Tier): Tier {
  if (sessions < 2) return "bar";
  const room = width - MEASURE.rowChrome - MEASURE.textMin - MEASURE.gap;
  const fits = (t: Tier, need: number) =>
    room >= need + (current !== undefined && RANK[t] > RANK[current] ? MEASURE.hysteresis : 0);
  if (fits("grid", sessions * pitch + MEASURE.bar)) return "grid";
  if (fits("strip", sessions * MEASURE.strip + MEASURE.count)) return "strip";
  return "bar";
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

/** Which questions in the column a focus lights: in one session, or in all of them. */
export function litTurns(data: DiscussionData, session: string, focus: Focus | null): Set<string> {
  if (!focus) return new Set();
  if (focus.turn) return new Set([focus.turn]);
  return new Set(data.turns
    .filter((t) => (session === ALL || t.session === session) && t.item === focus.item).map((t) => t.id));
}

/** Clicking a row the current session never asked jumps to the first session that
 *  did. All shows every session, so it never jumps. */
export function sessionForFocus(current: string, rowSessions: string[]): string {
  if (current === ALL) return current;
  return rowSessions.length && !rowSessions.includes(current) ? rowSessions[0] : current;
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
