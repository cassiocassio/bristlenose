/**
 * Board geometry for the Screens lens: where each sticky sits beside the screengrab, when a column
 * stacks, and the leader line from a card to its element. Pure functions, unit-tested; the lens
 * only measures and draws.
 *
 * Measured rules from the prototype (docs/design-screens.md S5):
 * - From 1100px of stage (--bn-breakpoint-content) quotes go either side, by which half of the page
 *   their element is in; below it, all on the right.
 * - A card wants to sit level with its element. Cards keep a gutter of --bn-space-md (12px).
 * - A column that would run past the screengrab stacks: evenly stepped, each card showing its
 *   timecode and first line, the later card over the earlier one's tail. Diagonal stacks slide each
 *   card a few pixels right, like a pad of stickies.
 */

export const WIDE_STAGE = 1100;
export const GUTTER = 12;
export const MIN_STEP = 46;

export type Side = "L" | "R";

export interface Box {
  /** x, y, w, h in 0–1 of the (cropped) screengrab. */
  x: number;
  y: number;
  w: number;
  h: number;
}

export function sideFor(box: Box, wide: boolean): Side {
  return wide && box.x + box.w / 2 < 0.5 ? "L" : "R";
}

export interface Placed {
  top: number;
  slide: number;
}

/**
 * Tops for a column of cards, in the order of their elements down the page.
 * `want` is where each card would like its top; `height` its measured height; `limit` the column's
 * height budget (the screengrab's height, at least 320).
 */
export function placeColumn(
  cards: { want: number; height: number }[],
  limit: number,
  diagonal = false,
): { placed: Placed[]; stacked: boolean; bottom: number } {
  if (cards.length === 0) return { placed: [], stacked: false, bottom: 0 };
  const placed: Placed[] = [];
  let y = 0;
  for (const c of cards) {
    const top = Math.max(c.want, y);
    placed.push({ top, slide: 0 });
    y = top + c.height + GUTTER;
  }
  const last = cards[cards.length - 1];
  const budget = Math.max(limit, 320);
  const overflow = placed[placed.length - 1].top + last.height > budget;
  if (!overflow || cards.length < 2) {
    return { placed, stacked: false, bottom: placed[placed.length - 1].top + last.height };
  }
  const start = Math.max(0, Math.min(cards[0].want, budget - last.height - MIN_STEP * (cards.length - 1)));
  const step = Math.max(MIN_STEP, (budget - start - last.height) / (cards.length - 1));
  const dx = diagonal ? Math.min(8, 40 / (cards.length - 1)) : 0;
  const stackedPlaced = cards.map((_, i) => ({ top: start + i * step, slide: i * dx }));
  return {
    placed: stackedPlaced,
    stacked: true,
    bottom: stackedPlaced[stackedPlaced.length - 1].top + last.height,
  };
}

export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * The leader from a card to its element: from whichever edge of the card faces the element, a
 * horizontal-in, horizontal-out curve, ending on the element's near edge. Coordinates are in the
 * board's space.
 */
export function leaderPath(card: Rect, element: Rect): { d: string; end: [number, number] } {
  const cardMid = card.left + card.width / 2;
  const elMid = element.left + element.width / 2;
  const fromRight = cardMid < elMid;
  const nx = fromRight ? card.left + card.width : card.left;
  const ny = card.top + 16;
  const hx = fromRight ? element.left - 3 : element.left + element.width + 3;
  const hy = element.top + element.height / 2;
  const mx = (nx + hx) / 2;
  return { d: `M${nx},${ny} C${mx},${ny} ${mx},${hy} ${hx},${hy}`, end: [hx, hy] };
}

// ── Arrangement: where the researcher put each card, per screengrab ─────────

export interface Spot {
  /** Fractions of the screengrab's width and height, from its top-left; may be < 0 or > 1. */
  x: number;
  y: number;
  /** Stacking order: the order of placing. */
  z: number;
}

const STORE_KEY = "bristlenose-screens-arrangement";

type Arrangement = Record<string, Spot>;

export function stillKey(sessionId: string, t: number): string {
  return `${sessionId}@${t}`;
}

function read(): Arrangement {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    const v = raw ? (JSON.parse(raw) as unknown) : {};
    return v && typeof v === "object" ? (v as Arrangement) : {};
  } catch {
    return {};
  }
}

function write(a: Arrangement): void {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(a));
  } catch {
    /* private window or full storage: the arrangement lasts the page */
  }
}

let memory: Arrangement | null = null;
const all = (): Arrangement => (memory ??= read());

export function spotsFor(still: string): Record<string, Spot> {
  const out: Record<string, Spot> = {};
  const prefix = `${still}/`;
  for (const [k, v] of Object.entries(all())) if (k.startsWith(prefix)) out[k.slice(prefix.length)] = v;
  return out;
}

export function topZ(): number {
  return Object.values(all()).reduce((m, s) => Math.max(m, s.z), 30);
}

export function putSpot(still: string, domId: string, spot: Spot): void {
  const a = { ...all(), [`${still}/${domId}`]: spot };
  memory = a;
  write(a);
}

export function clearSpots(still: string): void {
  const a = { ...all() };
  for (const k of Object.keys(a)) if (k.startsWith(`${still}/`)) delete a[k];
  memory = a;
  write(a);
}

/** Tests only. */
export function resetArrangementMemory(): void {
  memory = null;
}
