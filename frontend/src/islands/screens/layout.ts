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
 *   timecode and first line, the later card over the earlier one's tail. Stacks are straight: the
 *   prototype's diagonal variant (each card slid a few pixels right) was dropped with its picker.
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
}

/**
 * Tops for a column of cards, in the order of their elements down the page.
 * `want` is where each card would like its top; `height` its measured height; `limit` the column's
 * height budget (the screengrab's height, at least 320).
 */
export function placeColumn(
  cards: { want: number; height: number }[],
  limit: number,
): { placed: Placed[]; stacked: boolean; bottom: number } {
  if (cards.length === 0) return { placed: [], stacked: false, bottom: 0 };
  const placed: Placed[] = [];
  let y = 0;
  for (const c of cards) {
    const top = Math.max(c.want, y);
    placed.push({ top });
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
  const stackedPlaced = cards.map((_, i) => ({ top: start + i * step }));
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

/**
 * Kept in this browser's storage, keyed by the page's project id. Today that id is always "1"
 * (`data-project-id` is hard-coded in server/app.py and routes/export.py), so the key separates
 * arrangements by origin — the port the report is served on — and nothing finer: two projects
 * served on one port share them. The id is in the key so it becomes real with multi-project. Where
 * arrangements should live (a saved researcher edit, per project, perhaps in the export) is the
 * owner's call, docs/design-screens.md §6.9.
 */
const storeKey = (projectId: string) => `bristlenose-screens-arrangement-${projectId}`;

type Arrangement = Record<string, Spot>;

export function stillKey(sessionId: string, t: number): string {
  return `${sessionId}@${t}`;
}

function read(projectId: string): Arrangement {
  try {
    const raw = localStorage.getItem(storeKey(projectId));
    const v = raw ? (JSON.parse(raw) as unknown) : {};
    return v && typeof v === "object" ? (v as Arrangement) : {};
  } catch {
    return {};
  }
}

function write(projectId: string, a: Arrangement): void {
  try {
    localStorage.setItem(storeKey(projectId), JSON.stringify(a));
  } catch {
    /* private window or full storage: the arrangement lasts the page */
  }
}

const memory = new Map<string, Arrangement>();
function all(projectId: string): Arrangement {
  let a = memory.get(projectId);
  if (!a) {
    a = read(projectId);
    memory.set(projectId, a);
  }
  return a;
}

export function spotsFor(projectId: string, still: string): Record<string, Spot> {
  const out: Record<string, Spot> = {};
  const prefix = `${still}/`;
  for (const [k, v] of Object.entries(all(projectId))) if (k.startsWith(prefix)) out[k.slice(prefix.length)] = v;
  return out;
}

export function topZ(projectId: string): number {
  return Object.values(all(projectId)).reduce((m, s) => Math.max(m, s.z), 30);
}

export function putSpot(projectId: string, still: string, domId: string, spot: Spot): void {
  const a = { ...all(projectId), [`${still}/${domId}`]: spot };
  memory.set(projectId, a);
  write(projectId, a);
}

export function clearSpots(projectId: string, still: string): void {
  const a = { ...all(projectId) };
  for (const k of Object.keys(a)) if (k.startsWith(`${still}/`)) delete a[k];
  memory.set(projectId, a);
  write(projectId, a);
}

/** Tests only. */
export function resetArrangementMemory(): void {
  memory.clear();
}
