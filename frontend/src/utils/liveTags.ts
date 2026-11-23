/**
 * The AutoCode tags a running (or just-finished) run has landed on screen, and how every view
 * folds them into the data it already draws.
 *
 * Ordinary readers show nothing of a running first apply until its cut (D32), so the live page
 * takes the run's tentative and accepted tags from the playback store
 * (`contexts/AutoCodePlayback.ts`), which plays them out at a paced rate. That store publishes
 * the overlay below into the quotes store (`QuotesState.live`); these pure helpers merge it into
 * a quote card's tags, the tag counts and the filters, so no view shows a tag another has not
 * played yet.
 *
 * The overlay never draws a tag twice. A refetch can bring the same tag through the ordinary data
 * (the run's end hands over to it, docs/design-autocode-landing-plan.md Phase 4), so:
 * - a proposal the playback holds is drawn from the overlay only, never from the store's
 *   `proposedTags`, so a tentative tag the playback has not played is not shown either;
 * - an accepted tag the overlay shows is skipped when the store already has that tag on that
 *   quote;
 * - a tag the server has accepted and the playback has not yet played as accepted is held back
 *   from the store's tags (`waitingAccept`), so it turns green when its turn comes, not early.
 *
 * @module liveTags
 */

import type { ProposedTagBrief, TagResponse } from "./types";

export interface LiveTag {
  /** The proposal's id. */
  id: number;
  dom_id: string;
  tag_definition_id: number;
  tag_name: string;
  group_name: string;
  colour_set: string;
  colour_index: number;
  confidence: number;
  rationale: string;
  /** How the playback shows it now. */
  shown: "tentative" | "accepted";
  /** Landed as accepted in the last moment, and flashing. */
  flash: boolean;
}

export interface LiveOverlay {
  /** What the playback has landed, per quote. */
  byQuote: Record<string, LiveTag[]>;
  /** Every proposal id the playback holds, landed or not. */
  held: ReadonlySet<number>;
  /** `${dom_id}|${tag name, lower case}` of tags the server has accepted and the playback has not
   *  yet landed as accepted. */
  waitingAccept: ReadonlySet<string>;
}

export const EMPTY_LIVE: LiveOverlay = Object.freeze({
  byQuote: Object.freeze({}) as Record<string, LiveTag[]>,
  held: new Set<number>(),
  waitingAccept: new Set<string>(),
});

export function isLiveEmpty(live: LiveOverlay | undefined): boolean {
  return !live || live.held.size === 0;
}

const key = (domId: string, name: string) => `${domId}|${name.toLowerCase()}`;

/** A live accepted tag as the card's tag row draws a tag. */
export function liveTagAsTag(t: LiveTag): TagResponse {
  return {
    id: t.tag_definition_id,
    name: t.tag_name,
    codebook_group: t.group_name,
    colour_set: t.colour_set,
    colour_index: t.colour_index,
    source: "autocode",
  };
}

/** A live tentative tag as the card draws a proposal. */
export function liveTagAsProposal(t: LiveTag): ProposedTagBrief {
  return {
    id: t.id,
    tag_definition_id: t.tag_definition_id,
    tag_name: t.tag_name,
    group_name: t.group_name,
    colour_set: t.colour_set,
    colour_index: t.colour_index,
    confidence: t.confidence,
    rationale: t.rationale,
  };
}

/** A quote's accepted tags with the overlay folded in. Returns `tags` itself when the overlay
 *  changes nothing on this quote. */
export function mergedTags(domId: string, tags: TagResponse[], live: LiveOverlay | undefined): TagResponse[] {
  if (!live || isLiveEmpty(live)) return tags;
  const landed = live.byQuote[domId];
  let out = tags;
  if (live.waitingAccept.size > 0 && tags.some((t) => live.waitingAccept.has(key(domId, t.name)))) {
    out = tags.filter((t) => !live.waitingAccept.has(key(domId, t.name)));
  }
  if (landed) {
    for (const t of landed) {
      if (t.shown !== "accepted") continue;
      const lower = t.tag_name.toLowerCase();
      if (out.some((x) => x.name.toLowerCase() === lower)) continue;
      out = out === tags ? [...tags, liveTagAsTag(t)] : [...out, liveTagAsTag(t)];
    }
  }
  return out;
}

/** A quote's proposals with the overlay folded in: the store's minus the ones the playback holds,
 *  plus the ones it shows tentative, minus any tag the quote already has accepted. */
export function mergedProposals(
  domId: string,
  proposals: ProposedTagBrief[],
  acceptedTags: TagResponse[],
  live: LiveOverlay | undefined,
): ProposedTagBrief[] {
  if (!live || isLiveEmpty(live)) return proposals;
  const landed = live.byQuote[domId];
  let out = proposals.some((p) => live.held.has(p.id))
    ? proposals.filter((p) => !live.held.has(p.id))
    : proposals;
  if (landed) {
    for (const t of landed) {
      if (t.shown !== "tentative") continue;
      const lower = t.tag_name.toLowerCase();
      if (acceptedTags.some((x) => x.name.toLowerCase() === lower)) continue;
      out = [...out, liveTagAsProposal(t)];
    }
  }
  return out;
}

/** The names of a quote's tags flashing as they land accepted (`${domId}:${name}`, the card's
 *  `flashingTags` key). */
export function flashKeys(live: LiveOverlay | undefined): string[] {
  const out: string[] = [];
  if (!live) return out;
  for (const [domId, tags] of Object.entries(live.byQuote)) {
    for (const t of tags) if (t.flash && t.shown === "accepted") out.push(`${domId}:${t.tag_name}`);
  }
  return out;
}

/** The landed live tag behind an accepted tag a card draws, if the tag is only in the overlay
 *  (not yet a tag in the store): a removal of it goes to the playback store. */
export function liveAcceptedFor(
  domId: string,
  name: string,
  storeTags: TagResponse[],
  live: LiveOverlay | undefined,
): LiveTag | null {
  if (!live) return null;
  const lower = name.toLowerCase();
  if (storeTags.some((t) => t.name.toLowerCase() === lower && !live.waitingAccept.has(key(domId, t.name)))) {
    return null;
  }
  return (live.byQuote[domId] ?? []).find(
    (t) => t.shown === "accepted" && t.tag_name.toLowerCase() === lower,
  ) ?? null;
}

/** The overlay's tentative tag with this proposal id, if the playback shows it. */
export function liveTentative(domId: string, proposalId: number, live: LiveOverlay | undefined): LiveTag | null {
  if (!live) return null;
  return (live.byQuote[domId] ?? []).find((t) => t.id === proposalId && t.shown === "tentative") ?? null;
}

/**
 * The quotes' tags for filtering (search tokens, the tag filter) with the overlay folded in, so a
 * filtered Quotes list takes a new match live, in place (D10). Only the quotes the overlay
 * touches are rebuilt.
 */
export function mergedTagMap(
  tags: Record<string, TagResponse[]>,
  live: LiveOverlay | undefined,
  quoteTags: (domId: string) => TagResponse[],
): Record<string, TagResponse[]> {
  if (!live || isLiveEmpty(live)) return tags;
  const touched = new Set(Object.keys(live.byQuote));
  for (const k of live.waitingAccept) touched.add(k.slice(0, k.lastIndexOf("|")));
  if (touched.size === 0) return tags;
  const out = { ...tags };
  for (const domId of touched) {
    const base = tags[domId] ?? quoteTags(domId);
    const merged = mergedTags(domId, base, live);
    if (merged !== base) out[domId] = merged;
  }
  return out;
}
