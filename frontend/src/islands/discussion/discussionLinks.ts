/**
 * What the transcript needs from the Discussion lens's record, without loading the lens: which
 * moderator paragraphs ask a question of the guide, what the question's topic is, and the address
 * that opens the lens on it (docs/design-transcript-gutter.md, stage 3).
 */
import type { DiscussionData } from "./types";

export interface QuestionAsked {
  /** The merged guide item the turn asks. */
  item: string;
  /** Its short form, as the lens's navigator names it. */
  topic: string;
  /** The turn's id ("s1@01:16"), so the lens lands on this asking, not the item's first. */
  turn: string;
}

/** The router path into the Discussion lens, on one item as one turn asked it. */
export function discussionPath(item: string, turn: string): string {
  return `/report/discussion/?item=${encodeURIComponent(item)}&turn=${encodeURIComponent(turn)}`;
}

/** The arrival an address asked for: an item, and the turn that asked it. */
export function discussionArrival(query: URLSearchParams): { item: string; turn: string } | null {
  const item = query.get("item");
  const turn = query.get("turn");
  return item && turn ? { item, turn } : null;
}

/**
 * For one session: the questions its moderator asked, by the paragraph each was asked in. A turn
 * the model did not match to a guide item is not a question of the guide and gets no mark; a
 * paragraph that asks one item twice is marked once, at the first asking.
 */
export function questionsAsked(
  record: DiscussionData,
  sessionId: string,
  paragraphAt: (seconds: number) => number | null,
): Map<number, QuestionAsked[]> {
  const topics = new Map<string, string>();
  for (const section of record.sections ?? []) for (const it of section.items) topics.set(it.id, it.terse);
  for (const it of record.standalone ?? []) topics.set(it.id, it.terse);
  const out = new Map<number, QuestionAsked[]>();
  const turns = [...(record.turns ?? [])].filter((t) => t.session === sessionId && t.item).sort((a, b) => a.sec - b.sec);
  for (const t of turns) {
    const item = t.item!;
    const topic = topics.get(item);
    if (!topic) continue;
    const p = paragraphAt(t.sec);
    if (p === null) continue;
    const list = out.get(p) ?? [];
    if (!list.some((q) => q.item === item)) list.push({ item, topic, turn: t.id });
    out.set(p, list);
  }
  return out;
}
