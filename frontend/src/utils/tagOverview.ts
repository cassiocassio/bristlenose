/**
 * The tag sidebar's AutoCode overview, as pure arithmetic (docs/design-autocode-landing-plan.md
 * Phase 6: D12, D17, D19, D22). The component (`components/TagOverview.tsx`) draws what these
 * decide: which codebooks the line counts, what the line says, each chart's bands and the scale
 * each is drawn on.
 *
 * @module tagOverview
 */

import { binIndex } from "../components/ConfidenceHistogram";
import type { TickLines } from "../components/ConfidenceHistogram";
import { snapToStep } from "./confidenceStep";
import { growOnlyScale } from "./livePacing";
import { storedLinesOf } from "./recut";
import type { TagOverviewResponse, ZoneBin } from "./types";

/** The house default's lines: the ticks of a run not cut yet, and where a landing tentative tag
 *  below the lower line will be excluded at the cut (D5). */
export const DEFAULT_LINES = { lower: 0.3, upper: 0.7 } as const;

/** Machine-applied on every run, never reviewed: never on the overview's line (D17, D22). */
export const SENTIMENT_ID = "sentiment";

/** A codebook the overview may count: an installed, enabled codebook with its eye open, not
 *  Sentiment and not the researcher's own tags. Whether it has a run is the server's to say. */
export interface OverviewBook {
  id: string;
  title: string;
  /** Its tag definitions: the line's count. */
  tagCount: number;
}

/**
 * A codebook's ticks. After its cut, the lines it was cut at. During a first run, before any
 * cut: the lower line at the house default's 0.30 (D5), and the upper at the run's live accept
 * line (D47, D50), which only rises; none until the first batch has set one.
 */
export function ticksFor(c: TagOverviewResponse["codebooks"][number] | undefined): TickLines {
  const stored = c
    ? storedLinesOf({ applied_lower_threshold: c.lower, applied_upper_threshold: c.upper }, DEFAULT_LINES)
    : null;
  if (stored) return stored;
  const live = c?.live_accept_line;
  return { lower: DEFAULT_LINES.lower, upper: live == null ? null : snapToStep(live) };
}

export function emptyBins(): ZoneBin[] {
  return Array.from({ length: 20 }, () => ({ accepted: 0, tentative: 0, excluded: 0 }));
}

/** The server's bands, without their edges. */
export function zoneBins(bins: readonly ZoneBin[] | null | undefined): ZoneBin[] {
  const out = emptyBins();
  (bins ?? []).slice(0, 20).forEach((b, i) => {
    out[i] = { accepted: b.accepted, tentative: b.tentative, excluded: b.excluded };
  });
  return out;
}

/**
 * A run that is landing, as the page has played it (D19): the whole job's rows, accepted and
 * tentative as the cards show them, excluded as the playback holds them (`liveProposals`). A
 * tentative tag below the lower line is drawn excluded, where the run's cut will put it (D5).
 * Every row is counted once, from the playback alone: nothing from an older read is added.
 */
export function liveZoneBins(
  landed: readonly { confidence: number; shown: "tentative" | "accepted" | "excluded" }[],
  lower: number,
): ZoneBin[] {
  const out = emptyBins();
  for (const p of landed) {
    const bin = out[binIndex(p.confidence)];
    if (p.shown === "accepted") bin.accepted += 1;
    else if (p.shown === "excluded" || p.confidence < lower - 1e-9) bin.excluded += 1;
    else bin.tentative += 1;
  }
  return out;
}

/** Several codebooks' bands in one chart: each proposal sits where its own codebook put it. */
export function sumBins(all: readonly (readonly ZoneBin[])[]): ZoneBin[] {
  const out = emptyBins();
  for (const bins of all) {
    bins.forEach((b, i) => {
      out[i].accepted += b.accepted;
      out[i].tentative += b.tentative;
      out[i].excluded += b.excluded;
    });
  }
  return out;
}

export function tallyOf(bins: readonly ZoneBin[]): ZoneBin {
  return bins.reduce((t, b) => ({
      accepted: t.accepted + b.accepted,
      tentative: t.tentative + b.tentative,
      excluded: t.excluded + b.excluded,
    }), { accepted: 0, tentative: 0, excluded: 0 });
}

export function tallest(bins: readonly ZoneBin[]): number {
  return bins.reduce((m, b) => Math.max(m, b.accepted + b.tentative + b.excluded), 0);
}

/** A chart at rest: its tallest bar at full height, never fewer than five to a column. */
export function restScale(top: number): number {
  return Math.max(5, top);
}

export interface ScaleChart {
  id: string;
  bins: readonly ZoneBin[];
  /** A run is landing into this chart. */
  live: boolean;
}

/**
 * The scale every chart is drawn on (D19). At rest: the merged chart to its own tallest, the
 * split charts all to one shared scale so their sizes compare. While anything lands, a chart a
 * run lands into only grows, in rounded steps (`growOnlyScale`), from the scale it had; a
 * finished chart holds the scale it had. When the last run ends, everything rescales once.
 * `merged` names the merged chart's id; every other chart is a split one.
 */
export function nextScales(
  prev: Readonly<Record<string, number>> | null,
  charts: readonly ScaleChart[],
  merged: string,
): Record<string, number> {
  const books = charts.filter((c) => c.id !== merged);
  const shared = restScale(Math.max(0, ...books.map((c) => tallest(c.bins))));
  const rest = (c: ScaleChart) => (c.id === merged ? restScale(tallest(c.bins)) : shared);
  const out: Record<string, number> = {};
  const anyLive = charts.some((c) => c.live);
  for (const c of charts) {
    if (!anyLive) {
      out[c.id] = rest(c);
      continue;
    }
    const held = prev?.[c.id] ?? rest(c);
    out[c.id] = c.live ? growOnlyScale(held, tallest(c.bins)) : held;
  }
  return out;
}

export function sameScales(
  a: Readonly<Record<string, number>> | null,
  b: Readonly<Record<string, number>>,
): boolean {
  if (!a) return false;
  const ka = Object.keys(a);
  return ka.length === Object.keys(b).length && ka.every((k) => a[k] === b[k]);
}

/** Before any run, and in an export, the line counts every tag in the sidebar but Sentiment's
 *  (D22), and the codebooks that hold them. */
export function plainCounts(
  frameworks: readonly { id: string; groups: readonly { tags: readonly unknown[] }[] }[],
): { tags: number; codebooks: number } {
  let tags = 0;
  let codebooks = 0;
  for (const fw of frameworks) {
    if (fw.id === SENTIMENT_ID) continue;
    const n = fw.groups.reduce((s, g) => s + g.tags.length, 0);
    tags += n;
    if (n > 0) codebooks += 1;
  }
  return { tags, codebooks };
}

/**
 * Split a translated sentence around one inline element (`<link>…</link>`), so the words
 * before and after it can be the disclosure's and the element its own control. The key carries
 * the markup because word order varies: in Japanese the codebook count leads. Null when the
 * sentence has no such element.
 */
export function splitAround(
  text: string,
  tag: string,
): { before: string; inner: string; after: string } | null {
  const open = `<${tag}>`;
  const close = `</${tag}>`;
  const i = text.indexOf(open);
  const j = text.indexOf(close, i + open.length);
  if (i < 0 || j < 0) return null;
  return {
    before: text.slice(0, i),
    inner: text.slice(i + open.length, j),
    after: text.slice(j + close.length),
  };
}

/** A translated sentence as runs of text, each marked with the element it sits in, if any
 *  (`<exc>3</exc>`): the tally's numbers take their zone's colour. */
export function markupRuns(text: string, tags: readonly string[]): { text: string; tag: string | null }[] {
  const out: { text: string; tag: string | null }[] = [];
  const re = new RegExp(`<(${tags.join("|")})>(.*?)</\\1>`, "g");
  let at = 0;
  for (let m = re.exec(text); m !== null; m = re.exec(text)) {
    if (m.index > at) out.push({ text: text.slice(at, m.index), tag: null });
    out.push({ text: m[2], tag: m[1] });
    at = m.index + m[0].length;
  }
  if (at < text.length) out.push({ text: text.slice(at), tag: null });
  return out;
}
