/**
 * Board geometry for the Screens lens: where each sticky sits beside the screengrab, when a column
 * stacks, and the leader line from a card to its element. Pure functions, unit-tested; the lens
 * only measures and draws.
 *
 * Rules (docs/design-screens.md S5):
 * - Automatic placement never puts a card over the screengrab (the owner, 14 Oct 2026, reversing
 *   the prototype's overlapping edge): a card column sits beside it across a COLUMN_GUTTER the
 *   leader visibly crosses. Cards and gutter keep their size; the screengrab is what shrinks.
 * - Two columns when the stage fits both beside a screengrab of at least MIN_SHOT_W, either side
 *   by which half of the page each element is in; one column, on the right, when it fits one; below
 *   that, none: the screengrab takes the full width and its pinned cards lead the list under it. A
 *   column with no cards takes no room. A card the researcher drags goes wherever they put it.
 * - A card wants to sit level with its element. Cards in a column keep a gap of --bn-space-md (12px).
 * - A column that would run past the screengrab stacks: evenly stepped, each card showing its
 *   timecode and first line, the later card over the earlier one's tail. Stacks are straight: the
 *   prototype's diagonal variant (each card slid a few pixels right) was dropped with its picker.
 */

/** A card column's width: the cards keep this size whatever the stage. */
export const CARD_W = 270;
/** Between a card column and the screengrab: --bn-space-xl (2rem), in px at the default zoom. */
export const COLUMN_GUTTER = 32;
/** Below this width the screengrab stops being legible, so no column takes room from it. */
export const MIN_SHOT_W = 480;
/** Stage widths that fit two columns, and one, beside a legible screengrab. */
export const WIDE_STAGE = MIN_SHOT_W + 2 * (CARD_W + COLUMN_GUTTER); // 1084
export const ONE_COLUMN_STAGE = MIN_SHOT_W + CARD_W + COLUMN_GUTTER; // 782
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

/**
 * Which card columns the board draws: "lr", "l" or "r" beside the screengrab, or "none" when the
 * stage is too narrow for any (the pinned cards then join the list under it). `sides` is which
 * sides have a card to place. A stage of width 0 has not been measured (jsdom, the first layout):
 * it gets columns, never the narrow fallback.
 */
export type Columns = "lr" | "l" | "r" | "none";
export function boardColumns(stageW: number, sides: { L: boolean; R: boolean }): Columns {
  if (stageW > 0 && stageW < ONE_COLUMN_STAGE) return "none";
  if (sides.L && sides.R) return "lr";
  if (sides.L) return "l";
  if (sides.R) return "r";
  return "none";
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
//
// The owner, 14 Oct 2026: "if the user does nothing but resize, re-order automagically; if they
// reposition some or all cards, respect that work and intention but still re-organise the cards
// they didn't touch." So a placed card is stored as INTENT, not coordinates — which edge of the
// screengrab it sits beside, and how far down that edge as a fraction of the screengrab's height —
// and it moves with the image as the stage resizes. A card dropped over the screengrab keeps its
// place there (the researcher's choice; automatic placement never covers it).

export type Placement =
  /** Beside the screengrab: which side, and its top as a fraction of the screengrab's height. */
  | { kind: "edge"; side: Side; frac: number; z: number }
  /** Over the screengrab: its top-left as fractions of the screengrab's width and height. */
  | { kind: "over"; x: number; y: number; z: number };

/**
 * Kept in this browser's storage, keyed by the page's project id. Today that id is always "1"
 * (`data-project-id` is hard-coded in server/app.py and routes/export.py), so the key separates
 * arrangements by origin — the port the report is served on — and nothing finer: two projects
 * served on one port share them. The id is in the key so it becomes real with multi-project. Where
 * arrangements should live (a saved researcher edit, per project, perhaps in the export) is the
 * owner's call, docs/design-screens.md §6.9.
 */
const storeKey = (projectId: string) => `bristlenose-screens-placements-${projectId}`;
/** The first build's store: coordinates. Read once, converted to intent, then removed. */
const legacyKey = (projectId: string) => `bristlenose-screens-arrangement-${projectId}`;

type Arrangement = Record<string, Placement>;

export function stillKey(sessionId: string, t: number): string {
  return `${sessionId}@${t}`;
}

function isPlacement(v: unknown): v is Placement {
  if (!v || typeof v !== "object") return false;
  const p = v as Record<string, unknown>;
  if (p.kind === "edge") return (p.side === "L" || p.side === "R") && typeof p.frac === "number" && typeof p.z === "number";
  if (p.kind === "over") return typeof p.x === "number" && typeof p.y === "number" && typeof p.z === "number";
  return false;
}

/** A first-build spot {x, y, z} (top-left as fractions of the screengrab) as intent: left of the
 *  screengrab is the left edge, past its right edge the right, anything else was put over it. */
export function fromLegacy(spot: { x: number; y: number; z: number }): Placement {
  if (spot.x < 0) return { kind: "edge", side: "L", frac: spot.y, z: spot.z };
  if (spot.x >= 0.95) return { kind: "edge", side: "R", frac: spot.y, z: spot.z };
  return { kind: "over", x: spot.x, y: spot.y, z: spot.z };
}

function read(projectId: string): Arrangement {
  const out: Arrangement = {};
  try {
    const raw = localStorage.getItem(storeKey(projectId));
    const v = raw ? (JSON.parse(raw) as unknown) : {};
    if (v && typeof v === "object") for (const [k, p] of Object.entries(v)) if (isPlacement(p)) out[k] = p;
    const old = localStorage.getItem(legacyKey(projectId));
    if (old) {
      const legacy = JSON.parse(old) as Record<string, { x: number; y: number; z: number }>;
      for (const [k, spot] of Object.entries(legacy ?? {})) {
        if (!(k in out) && spot && typeof spot.x === "number" && typeof spot.y === "number") {
          out[k] = fromLegacy({ x: spot.x, y: spot.y, z: typeof spot.z === "number" ? spot.z : 31 });
        }
      }
      localStorage.setItem(storeKey(projectId), JSON.stringify(out));
      localStorage.removeItem(legacyKey(projectId));
    }
  } catch {
    /* unreadable or unavailable storage: start automatic */
  }
  return out;
}

function write(projectId: string, a: Arrangement): void {
  try {
    localStorage.setItem(storeKey(projectId), JSON.stringify(a));
  } catch {
    /* private window or full storage: the arrangement lasts the page */
  }
}

const memory = new Map<string, Arrangement>();
// A version that rises on every write, so a board — or an undo after the board has moved to another
// screen — re-reads the arrangement through useSyncExternalStore.
let version = 0;
const listeners = new Set<() => void>();
export function subscribeArrangement(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
export function arrangementVersion(): number {
  return version;
}
function store(projectId: string, a: Arrangement): void {
  memory.set(projectId, a);
  write(projectId, a);
  version++;
  for (const l of listeners) l();
}
function all(projectId: string): Arrangement {
  let a = memory.get(projectId);
  if (!a) {
    a = read(projectId);
    memory.set(projectId, a);
  }
  return a;
}

export function placementsFor(projectId: string, still: string): Record<string, Placement> {
  const out: Record<string, Placement> = {};
  const prefix = `${still}/`;
  for (const [k, v] of Object.entries(all(projectId))) if (k.startsWith(prefix)) out[k.slice(prefix.length)] = v;
  return out;
}

export function topZ(projectId: string): number {
  return Object.values(all(projectId)).reduce((m, s) => Math.max(m, s.z), 30);
}

export function putPlacement(projectId: string, still: string, domId: string, placement: Placement): void {
  const a = { ...all(projectId), [`${still}/${domId}`]: placement };
  store(projectId, a);
}

/** One card back to automatic placement. */
export function clearPlacement(projectId: string, still: string, domId: string): void {
  const a = { ...all(projectId) };
  delete a[`${still}/${domId}`];
  store(projectId, a);
}

/** A screengrab's whole arrangement, replaced: `{}` returns every card to automatic (Tidy); a
 *  saved copy puts it back (undo). */
export function setPlacements(projectId: string, still: string, placements: Record<string, Placement>): void {
  const a = { ...all(projectId) };
  for (const k of Object.keys(a)) if (k.startsWith(`${still}/`)) delete a[k];
  for (const [d, p] of Object.entries(placements)) a[`${still}/${d}`] = p;
  store(projectId, a);
}

/** Tests only. */
export function resetArrangementMemory(): void {
  memory.clear();
  version++;
}

// ── A column with hand-placed cards ─────────────────────────────────────────

export interface ColumnCard {
  id: string;
  height: number;
  /** Where its top would like to be: a placed card's spot, or level with an untouched card's element. */
  want: number;
  /** Placed by hand: it keeps its spot, and the untouched cards give way. */
  placed: boolean;
  /** Placing order, to keep the researcher's order between two placed cards at one height. */
  z?: number;
}

/**
 * Tops for a column that may hold hand-placed cards. Placed cards win: each sits at its own spot,
 * in the researcher's order, pushed down only as far as it takes not to overlap another placed
 * card. Untouched cards then re-flow around them, each in turn by its element's height into the
 * free slot nearest its anchor. A column with no placed card is the automatic column
 * (`placeColumn`, which stacks when it runs long); one with placed cards grows rather than stack,
 * so nobody's card is hidden under another's.
 */
export function arrangeColumn(
  cards: ColumnCard[],
  limit: number,
): { tops: Record<string, number>; stacked: boolean; bottom: number } {
  if (!cards.some((c) => c.placed)) {
    const order = [...cards].sort((a, b) => a.want - b.want);
    const { placed, stacked, bottom } = placeColumn(order, limit);
    const tops: Record<string, number> = {};
    order.forEach((c, i) => (tops[c.id] = placed[i].top));
    return { tops, stacked, bottom };
  }
  const tops: Record<string, number> = {};
  const taken: [number, number][] = [];
  const free = (y: number, h: number) =>
    y >= 0 && taken.every(([t, b]) => y + h + GUTTER <= t || y >= b + GUTTER);
  const own = cards.filter((c) => c.placed).sort((a, b) => a.want - b.want || (a.z ?? 0) - (b.z ?? 0));
  let floor = 0;
  for (const c of own) {
    const y = Math.max(c.want, floor);
    tops[c.id] = y;
    taken.push([y, y + c.height]);
    floor = y + c.height + GUTTER;
  }
  for (const c of cards.filter((c) => !c.placed).sort((a, b) => a.want - b.want)) {
    const candidates = [c.want, 0];
    for (const [t, b] of taken) candidates.push(t - c.height - GUTTER, b + GUTTER);
    const fits = candidates.filter((y) => free(y, c.height));
    const y = fits.reduce((best, y) => (Math.abs(y - c.want) < Math.abs(best - c.want) ? y : best), Infinity);
    const top = Number.isFinite(y) ? y : Math.max(0, ...taken.map(([, b]) => b + GUTTER));
    tops[c.id] = top;
    taken.push([top, top + c.height]);
  }
  const bottom = Math.max(0, ...cards.map((c) => tops[c.id] + c.height));
  return { tops, stacked: false, bottom };
}

/**
 * Where a card dropped at `card` (board coordinates) should live, as intent: beside the screengrab
 * on the side its centre fell, or over it. `shot` is the screengrab's rectangle in the same space.
 */
export function placementFromDrop(
  card: { left: number; top: number; width: number },
  shot: { left: number; top: number; width: number; height: number },
  z: number,
): Placement {
  const cx = card.left + card.width / 2;
  if (cx < shot.left) return { kind: "edge", side: "L", frac: (card.top - shot.top) / shot.height, z };
  if (cx > shot.left + shot.width) return { kind: "edge", side: "R", frac: (card.top - shot.top) / shot.height, z };
  return { kind: "over", x: (card.left - shot.left) / shot.width, y: (card.top - shot.top) / shot.height, z };
}
